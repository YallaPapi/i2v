"""
ComfyUI workflow templates for NSFW image generation.

These workflows define the node graphs for different generation types.
They're designed for img2img with various checkpoints.
"""

from typing import Literal


def build_i2i_workflow(
    checkpoint: str,
    vae: str,
    input_image: str,
    prompt: str,
    negative_prompt: str,
    width: int = 832,
    height: int = 1216,
    steps: int = 25,
    cfg: float = 7.0,
    denoise: float = 0.65,
    sampler: str = "euler_ancestral",
    scheduler: str = "normal",
    seed: int = -1,
) -> dict:
    """
    Build an img2img workflow for ComfyUI.

    Args:
        checkpoint: Name of the checkpoint file
        vae: Name of the VAE file
        input_image: Filename of the uploaded input image
        prompt: Positive prompt
        negative_prompt: Negative prompt
        width: Output width
        height: Output height
        steps: Sampling steps
        cfg: CFG scale
        denoise: Denoising strength (0.0-1.0)
        sampler: Sampler name
        scheduler: Scheduler name
        seed: Random seed (-1 for random)

    Returns:
        ComfyUI workflow dict
    """
    # Use random seed if -1
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        # Checkpoint loader
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint
            }
        },
        # VAE loader (separate for better quality)
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae
            }
        },
        # Load input image
        "3": {
            "class_type": "LoadImage",
            "inputs": {
                "image": input_image
            }
        },
        # Positive prompt (CLIP)
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1]  # From checkpoint loader
            }
        },
        # Negative prompt (CLIP)
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1]
            }
        },
        # Encode input image to latent
        "6": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["3", 0],  # From image loader
                "vae": ["2", 0]  # From VAE loader
            }
        },
        # Resize latent if needed
        "7": {
            "class_type": "LatentUpscale",
            "inputs": {
                "samples": ["6", 0],
                "upscale_method": "nearest-exact",
                "width": width,
                "height": height,
                "crop": "disabled"
            }
        },
        # KSampler for img2img
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],  # From checkpoint loader
                "positive": ["4", 0],  # Positive conditioning
                "negative": ["5", 0],  # Negative conditioning
                "latent_image": ["7", 0],  # From upscaled latent
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise
            }
        },
        # Decode latent to image
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],  # From KSampler
                "vae": ["2", 0]  # From VAE loader
            }
        },
        # Save image
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["9", 0],  # From VAE decode
                "filename_prefix": "nsfw_output"
            }
        }
    }

    return workflow


def build_i2i_workflow_with_lora(
    checkpoint: str,
    vae: str,
    lora_name: str,
    lora_strength: float,
    input_image: str,
    prompt: str,
    negative_prompt: str,
    width: int = 832,
    height: int = 1216,
    steps: int = 25,
    cfg: float = 7.0,
    denoise: float = 0.65,
    sampler: str = "euler_ancestral",
    scheduler: str = "normal",
    seed: int = -1,
) -> dict:
    """
    Build an img2img workflow with LoRA support.

    Same as build_i2i_workflow but adds a LoRA loader.
    """
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        # Checkpoint loader
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint
            }
        },
        # LoRA loader
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength
            }
        },
        # VAE loader
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae
            }
        },
        # Load input image
        "4": {
            "class_type": "LoadImage",
            "inputs": {
                "image": input_image
            }
        },
        # Positive prompt (using LoRA-modified CLIP)
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["2", 1]  # From LoRA loader
            }
        },
        # Negative prompt
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["2", 1]
            }
        },
        # Encode input image
        "7": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["3", 0]
            }
        },
        # Resize latent
        "8": {
            "class_type": "LatentUpscale",
            "inputs": {
                "samples": ["7", 0],
                "upscale_method": "nearest-exact",
                "width": width,
                "height": height,
                "crop": "disabled"
            }
        },
        # KSampler (using LoRA-modified model)
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],  # From LoRA loader
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["8", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise
            }
        },
        # Decode
        "10": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["9", 0],
                "vae": ["3", 0]
            }
        },
        # Save
        "11": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["10", 0],
                "filename_prefix": "nsfw_lora_output"
            }
        }
    }

    return workflow


# Default negative prompts for different styles
DEFAULT_NEGATIVE_PROMPTS = {
    "pony": (
        "score_4, score_3, score_2, score_1, "
        "lowres, bad anatomy, bad hands, text, error, missing fingers, "
        "extra digit, fewer digits, cropped, worst quality, low quality, "
        "normal quality, jpeg artifacts, signature, watermark, username, blurry, "
        "3d, render, doll, plastic, blur, haze, monochrome"
    ),
    "sdxl": (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, "
        "extra digit, fewer digits, cropped, worst quality, low quality, "
        "jpeg artifacts, signature, watermark, username, blurry, "
        "deformed, ugly, mutilated, disfigured, mutation, extra limbs"
    ),
}


# Pony-specific prompt boosters for quality
PONY_QUALITY_TAGS = "score_9, score_8_up, score_7_up, source_anime, "


def enhance_prompt_for_model(prompt: str, model_type: str) -> str:
    """
    Enhance a prompt with model-specific quality tags.

    Args:
        prompt: Original prompt
        model_type: "pony" or "sdxl"

    Returns:
        Enhanced prompt
    """
    if model_type == "pony":
        # Add Pony quality tags at the start
        return PONY_QUALITY_TAGS + prompt
    return prompt


# ============================================================================
# VIDEO WORKFLOWS
# ============================================================================


def build_animatediff_workflow(
    checkpoint: str,
    vae: str,
    motion_module: str,
    input_image: str,
    prompt: str,
    negative_prompt: str,
    width: int = 512,
    height: int = 768,
    steps: int = 20,
    cfg: float = 7.5,
    denoise: float = 0.75,
    frames: int = 16,
    fps: int = 8,
    seed: int = -1,
) -> dict:
    """
    Build an AnimateDiff workflow for video generation from image.

    Args:
        checkpoint: Name of the checkpoint file (SDXL-based)
        vae: Name of the VAE file
        motion_module: Name of the AnimateDiff motion module
        input_image: Filename of the uploaded input image
        prompt: Positive prompt
        negative_prompt: Negative prompt
        width: Output width
        height: Output height
        steps: Sampling steps
        cfg: CFG scale
        denoise: Denoising strength
        frames: Number of frames to generate
        fps: Frames per second for output
        seed: Random seed (-1 for random)

    Returns:
        ComfyUI workflow dict for AnimateDiff
    """
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        # Checkpoint loader
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint
            }
        },
        # VAE loader
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae
            }
        },
        # AnimateDiff motion module loader
        "3": {
            "class_type": "ADE_LoadAnimateDiffModel",
            "inputs": {
                "model_name": motion_module
            }
        },
        # Apply AnimateDiff to model
        "4": {
            "class_type": "ADE_ApplyAnimateDiffModel",
            "inputs": {
                "model": ["1", 0],
                "motion_model": ["3", 0],
            }
        },
        # Load input image
        "5": {
            "class_type": "LoadImage",
            "inputs": {
                "image": input_image
            }
        },
        # Positive prompt
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1]
            }
        },
        # Negative prompt
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1]
            }
        },
        # Encode input image to latent
        "8": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["5", 0],
                "vae": ["2", 0]
            }
        },
        # Create batch of latents from single image
        "9": {
            "class_type": "RepeatLatentBatch",
            "inputs": {
                "samples": ["8", 0],
                "amount": frames
            }
        },
        # KSampler with AnimateDiff model
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["9", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": denoise
            }
        },
        # Decode all frames
        "11": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["10", 0],
                "vae": ["2", 0]
            }
        },
        # Combine frames to video (using VHS nodes)
        "12": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["11", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": "animatediff_output",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            }
        }
    }

    return workflow


def build_svd_workflow(
    input_image: str,
    motion_bucket_id: int = 127,
    fps: int = 6,
    frames: int = 25,
    augmentation_level: float = 0.0,
    seed: int = -1,
) -> dict:
    """
    Build a Stable Video Diffusion (SVD) workflow.

    SVD uses a different architecture - it's purpose-built for video.

    Args:
        input_image: Filename of the uploaded input image
        motion_bucket_id: Motion intensity (1-255, higher = more motion)
        fps: Frames per second
        frames: Number of frames (14 or 25 for SVD-XT)
        augmentation_level: Noise augmentation (0.0-1.0)
        seed: Random seed

    Returns:
        ComfyUI workflow dict for SVD
    """
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        # Load SVD checkpoint
        "1": {
            "class_type": "ImageOnlyCheckpointLoader",
            "inputs": {
                "ckpt_name": "svd_xt.safetensors"
            }
        },
        # Load input image
        "2": {
            "class_type": "LoadImage",
            "inputs": {
                "image": input_image
            }
        },
        # Resize/prepare image for SVD (needs specific sizes)
        "3": {
            "class_type": "ImageResize",
            "inputs": {
                "image": ["2", 0],
                "width": 1024,
                "height": 576,
                "interpolation": "lanczos",
                "method": "fill / crop",
                "condition": "always",
            }
        },
        # SVD image conditioning
        "4": {
            "class_type": "SVD_img2vid_Conditioning",
            "inputs": {
                "clip_vision": ["1", 1],
                "init_image": ["3", 0],
                "vae": ["1", 2],
                "width": 1024,
                "height": 576,
                "video_frames": frames,
                "motion_bucket_id": motion_bucket_id,
                "fps": fps,
                "augmentation_level": augmentation_level,
            }
        },
        # KSampler for video generation
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["4", 1],
                "latent_image": ["4", 2],
                "seed": seed,
                "steps": 25,
                "cfg": 2.5,  # SVD uses lower CFG
                "sampler_name": "euler",
                "scheduler": "karras",
                "denoise": 1.0
            }
        },
        # Decode video latents
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2]
            }
        },
        # Combine to video
        "7": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["6", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": "svd_output",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            }
        }
    }

    return workflow


# Video workflow presets
VIDEO_PRESETS = {
    "animatediff_subtle": {
        "motion_module": "mm_sd_v15_v2.ckpt",
        "frames": 16,
        "fps": 8,
        "denoise": 0.65,
        "description": "Subtle motion, good for portraits",
    },
    "animatediff_dynamic": {
        "motion_module": "mm_sd_v15_v2.ckpt",
        "frames": 24,
        "fps": 12,
        "denoise": 0.80,
        "description": "More dynamic motion",
    },
    "svd_standard": {
        "model": "svd_xt.safetensors",
        "frames": 25,
        "fps": 6,
        "motion_bucket_id": 127,
        "description": "Standard SVD-XT video generation",
    },
    "svd_high_motion": {
        "model": "svd_xt.safetensors",
        "frames": 25,
        "fps": 8,
        "motion_bucket_id": 200,
        "description": "Higher motion intensity",
    },
}


# ============================================================================
# NSFW PRESETS
# ============================================================================

# Preset configurations for different NSFW styles
NSFW_PRESETS = {
    "anime_lewd": {
        "model_type": "pony",
        "checkpoint": "ponyDiffusionV6XL_v6.safetensors",
        "steps": 25,
        "cfg": 7.0,
        "denoise": 0.65,
        "sampler": "euler_ancestral",
    },
    "anime_explicit": {
        "model_type": "pony",
        "checkpoint": "ponyDiffusionV6XL_v6.safetensors",
        "steps": 30,
        "cfg": 8.0,
        "denoise": 0.75,
        "sampler": "euler_ancestral",
    },
    "realistic_lewd": {
        "model_type": "pony",
        "checkpoint": "ponyRealism_v21.safetensors",
        "steps": 30,
        "cfg": 6.5,
        "denoise": 0.60,
        "sampler": "dpmpp_2m",
    },
    "realistic_explicit": {
        "model_type": "pony",
        "checkpoint": "ponyRealism_v21.safetensors",
        "steps": 35,
        "cfg": 7.0,
        "denoise": 0.70,
        "sampler": "dpmpp_2m",
    },
}


# =============================================================================
# WAN 2.2 IMAGE-TO-VIDEO WORKFLOWS
# =============================================================================

# Wan 2.2 model configuration
WAN_MODELS = {
    "unet_high": "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
    "unet_low": "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
    "text_encoder": "nsfw_wan_umt5-xxl_fp8_scaled.safetensors",
    "vae": "wan_2.1_vae.safetensors",
    "lora_high": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
}

WAN_MODEL_URLS = {
    "unet_high": "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
    "unet_low": "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
    "text_encoder": "https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors",
    "vae": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
    "lora_high": "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low": "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
}

# Model paths on vast.ai instance (relative to /workspace/ComfyUI/models/)
WAN_MODEL_PATHS = {
    "unet_high": "unet/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
    "unet_low": "unet/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
    "text_encoder": "text_encoders/nsfw_wan_umt5-xxl_fp8_scaled.safetensors",
    "vae": "vae/wan_2.1_vae.safetensors",
    "lora_high": "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low": "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
}


def build_wan22_i2v_workflow(
    image_filename: str,
    prompt: str,
    negative_prompt: str = "",
    num_frames: int = 81,
    steps: int = 4,
    cfg_scale: float = 1.0,
    seed: int = -1,
    width: int = 832,
    height: int = 480,
) -> dict:
    """
    Build a ComfyUI workflow for Wan 2.2 image-to-video generation.

    Uses GGUF quantized models and LightX2V LoRAs for fast 4-step generation.

    Args:
        image_filename: Name of image file already uploaded to ComfyUI input folder
        prompt: Text prompt describing the desired video motion/content
        negative_prompt: Negative prompt (what to avoid)
        num_frames: Number of frames to generate (81 = ~3.4s at 24fps)
        steps: Number of sampling steps (4 for LightX2V, can use more for quality)
        cfg_scale: Classifier-free guidance scale (1.0 recommended for LightX2V)
        seed: Random seed (-1 for random)
        width: Output video width
        height: Output video height

    Returns:
        ComfyUI workflow dict ready to submit to /prompt API
    """
    import random as rand_module
    if seed == -1:
        seed = rand_module.randint(0, 2**32 - 1)

    workflow = {
        # Node 1: Load GGUF UNet model (high noise variant for I2V)
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": WAN_MODELS["unet_high"],
            },
        },
        # Node 2: Load text encoder (CLIP for Wan)
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": WAN_MODELS["text_encoder"],
                "type": "wan",
            },
        },
        # Node 3: Load VAE
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": WAN_MODELS["vae"],
            },
        },
        # Node 4: Load LightX2V LoRA (model only, no CLIP)
        "4": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": WAN_MODELS["lora_high"],
                "strength_model": 1.0,
                "model": ["1", 0],  # Connect to UNet loader output
            },
        },
        # Node 5: Load input image
        "5": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename,
            },
        },
        # Node 6: Encode positive prompt
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["2", 0],  # Connect to CLIP loader
            },
        },
        # Node 7: Encode negative prompt
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt or "blurry, low quality, distorted, watermark",
                "clip": ["2", 0],  # Connect to CLIP loader
            },
        },
        # Node 8: Wan Image to Video sampler
        "8": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "model": ["4", 0],  # Connect to LoRA-applied model
                "positive": ["6", 0],  # Positive conditioning
                "negative": ["7", 0],  # Negative conditioning
                "vae": ["3", 0],  # VAE
                "image": ["5", 0],  # Input image
                "width": width,
                "height": height,
                "num_frames": num_frames,
                "steps": steps,
                "cfg": cfg_scale,
                "seed": seed,
            },
        },
        # Node 9: Combine frames to video
        "9": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["8", 0],  # Frames from sampler
                "frame_rate": 24,
                "loop_count": 0,
                "filename_prefix": "wan22_i2v",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }

    return workflow
