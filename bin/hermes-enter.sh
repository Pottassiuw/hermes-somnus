#!/bin/sh
# Install root-owned, 0755; forced SSH command, never an optional model wrapper.
# Container creation, fixed mounts and cleanup belong to the trusted service.
set -eu
exec /usr/bin/docker exec -i --user 65532:65532 --workdir /work \
  hermes-author /bin/bash -lc "${SSH_ORIGINAL_COMMAND:?No command supplied}"
