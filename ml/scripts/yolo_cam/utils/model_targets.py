import numpy as np
import torch
import torchvision


class ClassifierOutputTarget:
    def __init__(self, category):
        self.category = category

    def __call__(self, model_output):
        if len(model_output.shape) == 1:
            return model_output[self.category]
        return model_output[:, self.category]


class YOLOBoxScoreTarget:
    """Target for YOLO detection/OBB decoded outputs.

    Expects tensors shaped as [B, C, N], where the first 4 channels are boxes,
    the last `num_extra_channels` channels are task-specific extras (e.g. angle in OBB),
    and the channels in between are class confidences.
    """

    def __init__(
        self,
        category: int | None = None,
        num_extra_channels: int = 0,
        target_xy: tuple[float, float] | None = None,
        distance_sigma: float = 96.0,
    ):
        self.category = category
        self.num_extra_channels = num_extra_channels
        self.target_xy = target_xy
        self.distance_sigma = max(float(distance_sigma), 1.0)

    def __call__(self, model_output):
        if isinstance(model_output, (list, tuple)):
            model_output = model_output[0]

        if not torch.is_tensor(model_output):
            raise TypeError(f"Unsupported YOLO output type for CAM target: {type(model_output)!r}")

        if model_output.ndim == 2:
            model_output = model_output.unsqueeze(0)

        if model_output.ndim != 3:
            raise ValueError(f"Expected YOLO output with shape [B, C, N], got {tuple(model_output.shape)}")

        cls_start = 4
        cls_end = model_output.shape[1] - self.num_extra_channels
        class_scores = model_output[:, cls_start:cls_end, :]

        if class_scores.numel() == 0:
            raise ValueError(
                f"No class-score channels found in YOLO output with shape {tuple(model_output.shape)} "
                f"and num_extra_channels={self.num_extra_channels}"
            )

        selected_scores = class_scores[:, self.category, :] if self.category is not None and 0 <= self.category < class_scores.shape[1] else class_scores.max(dim=1).values

        if self.target_xy is None:
            return selected_scores.max()

        box_centers = model_output[:, 0:2, :]
        target_xy = box_centers.new_tensor(self.target_xy).view(1, 2, 1)
        distances = torch.linalg.norm(box_centers - target_xy, dim=1)
        spatial_prior = torch.exp(-distances / self.distance_sigma)
        combined_score = selected_scores * spatial_prior
        best_idx = combined_score.argmax(dim=-1, keepdim=True)
        return selected_scores.gather(dim=-1, index=best_idx).max()


class ClassifierOutputSoftmaxTarget:
    def __init__(self, category):
        self.category = category

    def __call__(self, model_output):
        if len(model_output.shape) == 1:
            return torch.softmax(model_output, dim=-1)[self.category]
        return torch.softmax(model_output, dim=-1)[:, self.category]


class BinaryClassifierOutputTarget:
    def __init__(self, category):
        self.category = category

    def __call__(self, model_output):
        if self.category == 1:
            sign = 1
        else:
            sign = -1
        return model_output * sign


class SoftmaxOutputTarget:
    def __init__(self):
        pass

    def __call__(self, model_output):
        return torch.softmax(model_output, dim=-1)


class RawScoresOutputTarget:
    def __init__(self):
        pass

    def __call__(self, model_output):
        return model_output


class SemanticSegmentationTarget:
    """ Gets a binary spatial mask and a category,
        And return the sum of the category scores,
        of the pixels in the mask. """

    def __init__(self, category, mask):
        self.category = category
        self.mask = torch.from_numpy(mask)
        if torch.cuda.is_available():
            self.mask = self.mask.cuda()

    def __call__(self, model_output):
        return (model_output[self.category, :, :] * self.mask).sum()


class FasterRCNNBoxScoreTarget:
    """ For every original detected bounding box specified in "bounding boxes",
        assign a score on how the current bounding boxes match it,
            1. In IOU
            2. In the classification score.
        If there is not a large enough overlap, or the category changed,
        assign a score of 0.

        The total score is the sum of all the box scores.
    """

    def __init__(self, labels, bounding_boxes, iou_threshold=0.5):
        self.labels = labels
        self.bounding_boxes = bounding_boxes
        self.iou_threshold = iou_threshold

    def __call__(self, model_outputs):
        output = torch.Tensor([0])
        if torch.cuda.is_available():
            output = output.cuda()

        if len(model_outputs["boxes"]) == 0:
            return output

        for box, label in zip(self.bounding_boxes, self.labels):
            box = torch.Tensor(box[None, :])
            if torch.cuda.is_available():
                box = box.cuda()

            ious = torchvision.ops.box_iou(box, model_outputs["boxes"])
            index = ious.argmax()
            if ious[0, index] > self.iou_threshold and model_outputs["labels"][index] == label:
                score = ious[0, index] + model_outputs["scores"][index]
                output = output + score
        return output
