"""
Modal configuration and image setup
"""

import modal

# Create Modal app
app = modal.App("website-builder-api")

# Build the agent image with all required dependencies
agent_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "ca-certificates", "gnupg", "sudo")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs"
    )
    .run_commands("npm install -g pnpm")
    .pip_install_from_requirements("requirements.txt")
    .run_commands(
        "useradd -m -s /bin/bash -u 1000 claudeuser",
        "mkdir -p /home/claudeuser/.local/bin /home/claudeuser/.local/share /home/claudeuser/.cache",
        "chown -R claudeuser:claudeuser /home/claudeuser",
        "chmod -R 755 /home/claudeuser",
        "echo 'claudeuser ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/npm, /usr/sbin/update-ca-certificates' >> /etc/sudoers"
    )
    .env({"PATH": "/home/claudeuser/.local/bin:$PATH", "SHELL": "/bin/bash", "HOME": "/home/claudeuser"})
    # Install Claude Code CLI which is required by the Python SDK
    .run_commands(
        "su - claudeuser -c 'curl -fsSL https://claude.ai/install.sh | bash'"
    )
    .add_local_python_source("config", "models", "routes", "dev_server", "agent")
)

# Create Modal Dicts for persistent storage
sessions = modal.Dict.from_name("sessions", create_if_missing=True)
ws_urls = modal.Dict.from_name("ws_urls", create_if_missing=True)
