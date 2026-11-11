# Radiant + prjoxide fuzzing image (linux/amd64; runs under Rosetta on Apple Silicon).
# Radiant itself is NOT in the image: it is installed once into the bind-mounted
# /opt/lscc (host ~/lscc) so the image never contains Lattice files.
FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential pkg-config \
        python3 python3-dev python3-pip \
        libxft2 libxext6 libxrender1 libxtst6 libxi6 libsm6 libice6 \
        libfreetype6 libfontconfig1 libglib2.0-0 libgl1 libxcb1 libx11-xcb1 \
        libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 libnss3 libasound2 \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
        libxcb-xkb1 libxcb-xfixes0 libxcb-shm0 libxcb-sync1 libxcb-render0 \
        libopengl0 libegl1 \
        libtinfo5 libncurses5 libusb-0.1-4 libusb-1.0-0 \
        unzip xz-utils file procps less locales \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8

# radiant_env sets LANG=en_US.UTF-8; ipgen's Python aborts with
# "locale.Error: unsupported locale setting" if that locale is missing.
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# Rust for libprjoxide / pyprjoxide (built inside the container, amd64 target dir)
ENV RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/rust PATH=/opt/rust/bin:$PATH
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

ENV RADIANTDIR=/opt/lscc/radiant/2026.1 \
    CARGO_TARGET_DIR=/work/target-amd64
WORKDIR /work/prjoxide
CMD ["bash"]
