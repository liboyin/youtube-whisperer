FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04

ARG APT_PROXY
ARG PYPI_PROXY

ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_DRIVER_CAPABILITIES=all \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspaces/youtube-whisperer

# Install OS packages and pinned Python dependencies first, so editing source does not
# invalidate these layers and force a full dependency reinstall on every rebuild.
#
# The apt/pip steps use the shared build helpers, supplied as the named build context
# `build_common` and pinned in docker-compose.cpu.yaml. They are bind-mounted rather than
# copied: they are build-time only, so nothing is left behind in the image. A build that
# bypasses compose must supply the context itself, otherwise BuildKit looks for an image
# by that name on Docker Hub:
#   docker buildx build --build-context build_common=<git-url-or-local-clone> .
RUN --mount=type=bind,from=build_common,target=/build-common \
    /build-common/apt_install.sh curl ffmpeg git python3 python3-pip unzip

# Deno is yt-dlp's JavaScript runtime (`js_runtimes` in youtube_whisperer/downloaders/).
# The symlink exposes the distro's python3 as `python`, which the compose entrypoints call.
RUN export DENO_INSTALL=/usr/local && curl -fsSL https://deno.land/install.sh | sh \
    && ln -s "$(which python3)" "$(dirname "$(which python3)")/python"

COPY --chown=ubuntu requirements.txt ./
RUN --mount=type=bind,from=build_common,target=/build-common \
    /build-common/pip_install.sh requirements.txt

# Copy the rest of the source and install the project itself in editable mode.
COPY --chown=ubuntu . .
RUN pip install -e .

USER ubuntu
