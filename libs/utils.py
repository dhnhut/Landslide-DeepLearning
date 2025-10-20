# Device
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image

def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def visualize_comparison(left_img_path, right_img_path, left_title='Original', right_title='After Image'):
    # Set seaborn style
    sns.set_style("whitegrid")

    # Create figure with subplots
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    # Load and display original image
    img = Image.open(left_img_path)
    axes[0].imshow(img)
    axes[0].set_title(left_title, fontsize=14, fontweight='bold')
    axes[0].axis('off')

    # Load and display prediction mask
    pred_img = Image.open(right_img_path)
    axes[1].imshow(pred_img, cmap='gray')
    axes[1].set_title(right_title, fontsize=14, fontweight='bold')
    axes[1].axis('off')

    plt.tight_layout()
    plt.show()