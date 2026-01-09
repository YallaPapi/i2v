# ComfyUI GPU Image for vast.ai
# Pre-baked with NSFW models for fast cold starts
#
# Build: docker build -t comfyui-nsfw:latest .
# Push:  docker push your-registry/comfyui-nsfw:latest
#
# Note: Building requires ~60GB disk and takes 30-60 minutes
# to download all models.

FROM ai-dock/comfyui:latest

USER root

# Install additional dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

# Set model directories
ENV MODEL_DIR=/opt/ComfyUI/models
ENV CHECKPOINTS_DIR=${MODEL_DIR}/checkpoints
ENV VAE_DIR=${MODEL_DIR}/vae
ENV LORA_DIR=${MODEL_DIR}/loras
ENV VID_DIR=${MODEL_DIR}/diffusion_models

# Create directories
RUN mkdir -p ${CHECKPOINTS_DIR} ${VAE_DIR} ${LORA_DIR} ${VID_DIR}

# Download wget options for reliable transfers
ENV WGET_OPTS="--progress=dot:giga --retry-connrefused --tries=5 --continue"

# ============================================================================
# TIER 1: ESSENTIAL MODELS (Always included)
# ============================================================================

# Pony Diffusion V6 XL - Best for anime/stylized NSFW (~6.5GB)
RUN wget ${WGET_OPTS} -O ${CHECKPOINTS_DIR}/ponyDiffusionV6XL_v6.safetensors \
    "https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors"

# SDXL Base 1.0 - General purpose (~6.9GB)
RUN wget ${WGET_OPTS} -O ${CHECKPOINTS_DIR}/sd_xl_base_1.0.safetensors \
    "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"

# SDXL VAE - Required for all SDXL models (~335MB)
RUN wget ${WGET_OPTS} -O ${VAE_DIR}/sdxl_vae.safetensors \
    "https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors"

# ============================================================================
# TIER 2: ENHANCED MODELS (Photorealistic humans)
# ============================================================================

# RealVisXL V4.0 - Excellent photorealistic humans (~6.5GB)
RUN wget ${WGET_OPTS} -O ${CHECKPOINTS_DIR}/RealVisXL_V4.0.safetensors \
    "https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors" || true

# Juggernaut XL V9 - Great skin textures (~6.5GB)
RUN wget ${WGET_OPTS} -O ${CHECKPOINTS_DIR}/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors \
    "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors" || true

# ============================================================================
# CUSTOM NODES
# ============================================================================

# Video Helper Suite - For video output/encoding
RUN cd /opt/ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git || true

# AnimateDiff Evolved - For AnimateDiff video generation
RUN cd /opt/ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git || true

# ComfyUI Manager - For managing nodes
RUN cd /opt/ComfyUI/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git || true

# Install dependencies for custom nodes
RUN cd /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && \
    pip install -r requirements.txt || true
RUN cd /opt/ComfyUI/custom_nodes/ComfyUI-AnimateDiff-Evolved && \
    pip install -r requirements.txt || true

# ============================================================================
# STARTUP SCRIPT
# ============================================================================

# Copy helper scripts
COPY download_lora.sh /opt/scripts/download_lora.sh
RUN chmod +x /opt/scripts/download_lora.sh

# Add script to download Pony Realism if URL provided at runtime
COPY startup.sh /opt/scripts/startup.sh
RUN chmod +x /opt/scripts/startup.sh

# Set ownership
RUN chown -R 1000:1000 ${MODEL_DIR} /opt/scripts

USER 1000

# Expose ComfyUI port
EXPOSE 8188

# Use custom startup that handles additional model downloads
ENTRYPOINT ["/opt/scripts/startup.sh"]
