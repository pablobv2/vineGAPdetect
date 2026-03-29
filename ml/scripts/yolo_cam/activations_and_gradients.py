import numpy as np
import torch


class ActivationsAndGradients:
    """ Class for extracting activations and
    registering gradients from targetted intermediate layers """

    def __init__(self, model, target_layers, reshape_transform):
        self.model = model
        self.gradients = []
        self.activations = []
        self.reshape_transform = reshape_transform
        self.handles = []
        for target_layer in target_layers:
            self.handles.append(
                target_layer.register_forward_hook(self.save_activation))
            # Because of https://github.com/pytorch/pytorch/issues/61519,
            # we don't use backward hook to record gradients.
            self.handles.append(
                target_layer.register_forward_hook(self.save_gradient))

    def _clone_inference_tensors(self, value):
        if torch.is_tensor(value):
            return value.clone() if value.is_inference() else value
        if isinstance(value, dict):
            changed = False
            cloned = {}
            for key, item in value.items():
                cloned_item = self._clone_inference_tensors(item)
                cloned[key] = cloned_item
                changed = changed or cloned_item is not item
            return cloned if changed else value
        if isinstance(value, list):
            cloned = [self._clone_inference_tensors(item) for item in value]
            return cloned if any(cloned_item is not item for cloned_item, item in zip(cloned, value)) else value
        if isinstance(value, tuple):
            cloned = tuple(self._clone_inference_tensors(item) for item in value)
            return cloned if any(cloned_item is not item for cloned_item, item in zip(cloned, value)) else value
        return value

    def _reset_inference_caches(self, model):
        try:
            head = model.model[-1]
        except Exception:
            return

        for name, value in vars(head).items():
            cloned = self._clone_inference_tensors(value)
            if cloned is not value:
                setattr(head, name, cloned)

    def save_activation(self, module, input, output):
        activation = output

        if self.reshape_transform is not None:
            activation = self.reshape_transform(activation)
        self.activations.append(activation.cpu().detach())

    def save_gradient(self, module, input, output):
        if not hasattr(output, "requires_grad") or not output.requires_grad:
            # You can only register hooks on tensor requires grad.
            return

        # Gradients are computed in reverse order
        def _store_grad(grad):
            if self.reshape_transform is not None:
                grad = self.reshape_transform(grad)
            self.gradients = [grad.cpu().detach()] + self.gradients

        output.register_hook(_store_grad)

    def __call__(self, x):
        self.gradients = []
        self.activations = []
        model = self.model.model if hasattr(self.model, "model") else self.model
        self._reset_inference_caches(model)

        if isinstance(x, np.ndarray):
            if x.ndim == 3:
                x = x[:, :, ::-1].transpose(2, 0, 1)
                x = np.ascontiguousarray(x)
                x = torch.from_numpy(x).float().unsqueeze(0) / 255.0
            elif x.ndim == 4:
                x = torch.from_numpy(np.ascontiguousarray(x)).float()
            else:
                raise ValueError(f"Unsupported numpy input shape for CAM: {x.shape}")

        if isinstance(x, torch.Tensor):
            if x.ndim == 3:
                x = x.unsqueeze(0)
            device = next(model.parameters()).device
            x = x.to(device)

        return model(x)

    def release(self):
        for handle in self.handles:
            handle.remove()
