import numpy as np
from yolo_cam.base_cam import BaseCAM

class GradCAM(BaseCAM):
    def __init__(self, model, target_layers, task: str = 'od', reshape_transform=None):
        # Grad-CAM necesita los gradientes, así que nos aseguramos de que uses_gradients sea True.
        # La clase BaseCAM ya lo hace por defecto, así que solo llamamos al constructor padre.
        super(GradCAM, self).__init__(model, target_layers, task, reshape_transform=reshape_transform)

    def get_cam_weights(self,
                        input_tensor,
                        target_layer,
                        target_category,
                        activations,
                        grads):
        """
        Calcula los pesos de los canales para Grad-CAM.

        El peso para cada canal del mapa de características es el promedio global (Global Average Pooling)
        del gradiente de ese canal.
        """
        # Esta es la operación clave de Grad-CAM:
        # Para cada canal, calcula el valor medio de sus gradientes.
        # grads tiene forma (canales, altura, anchura)
        # axis=(1, 2) promedia sobre las dimensiones de altura y anchura.
        if grads.ndim == 4:
            return np.mean(grads, axis=(2, 3))
        return np.mean(grads, axis=(1, 2))
