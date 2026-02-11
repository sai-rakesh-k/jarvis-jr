"""
Docker sandbox for isolated command execution with container reuse
"""
import docker
import os
from typing import Tuple, Optional
from .config import config


class DockerSandbox:
    """Manages Docker containers for safe command execution"""
    def __init__(self):
        """Initialize Docker client and configuration"""
        self.config = config
        self.client = self._get_docker_client()
        self._ensure_image_exists()
        self._persistent_container = None  # Reusable container
        self._mounted_dir = None  # Track mounted directory

    def _get_docker_client(self):
        """
        Create Docker client with explicit health check.
        This avoids false negatives on Docker Desktop + WSL.
        """
        try:
            # Force correct socket for Docker Desktop
            os.environ.setdefault("DOCKER_HOST", "unix:///var/run/docker.sock")

            client = docker.from_env()
            client.ping()  # Explicit daemon health check
            return client

        except Exception as e:
            raise RuntimeError(
                "Docker is not available.\n"
                "Please ensure:\n"
                "1) Docker Desktop is running\n"
                "2) WSL integration is enabled\n"
                "3) Docker Desktop shows 'Running'"
            ) from e

    def _ensure_image_exists(self):
        """Build Docker image if it doesn't exist"""
        try:
            self.client.images.get(self.config.docker_image)
        except docker.errors.ImageNotFound:
            print(f"Building Docker image '{self.config.docker_image}'...")
            print("This may take a few minutes on first run...")

            # Locate Dockerfile in project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            dockerfile_path = os.path.join(project_root, "Dockerfile")

            if not os.path.exists(dockerfile_path):
                raise FileNotFoundError(
                    f"Dockerfile not found at {dockerfile_path}"
                )

            # Build image
            self.client.images.build(
                path=project_root,
                tag=self.config.docker_image,
                rm=True
            )

            print(f"✓ Docker image '{self.config.docker_image}' built successfully!")

    def _get_or_create_container(self, working_dir: Optional[str] = None):
        """
        Get existing container or create a new one
        
        Args:
            working_dir: Directory to mount in container
            
        Returns:
            Running Docker container
        """
        # If container reuse is disabled, always return None (will create new)
        if not getattr(self.config, "reuse_container", False):
            return None
        
        # Check if we have a persistent container
        if self._persistent_container:
            try:
                # Refresh container state
                self._persistent_container.reload()
                
                # Check if container is still running
                if self._persistent_container.status == "running":
                    # Check if same directory is mounted (or both None)
                    if self._mounted_dir == working_dir:
                        return self._persistent_container  # Reuse existing!
                    else:
                        # Different directory - need to recreate
                        self._stop_persistent_container()
                        
            except docker.errors.NotFound:
                # Container was removed externally
                self._persistent_container = None
            except (docker.errors.APIError, Exception):
                # Container in bad state or API error
                self._stop_persistent_container()
        
        # Create new persistent container
        return self._create_persistent_container(working_dir)

    def _create_persistent_container(self, working_dir: Optional[str] = None):
        """
        Create a new long-running container
        
        Args:
            working_dir: Directory to mount
            
        Returns:
            New Docker container
        """
        volumes = {}
        container_workdir = "/workspace"
        
        if working_dir:
            volumes[os.path.abspath(working_dir)] = {
                "bind": container_workdir,
                "mode": "rw"
            }
        
        # Create container that stays alive
        container = self.client.containers.run(
            image=self.config.docker_image,
            command=["sleep", "infinity"],  # Keep container alive
            volumes=volumes,
            working_dir=container_workdir,
            detach=True,
            mem_limit=self.config.docker_memory_limit,
            cpu_quota=int(self.config.docker_cpu_limit * 100000),
            network_mode="none",  # Disable networking for extra safety
            remove=False,
            tty=True
        )
        
        self._persistent_container = container
        self._mounted_dir = working_dir
        
        return container

    def _stop_persistent_container(self):
        """Stop and remove persistent container efficiently"""
        if self._persistent_container:
            try:
                # Try to stop gracefully first (2 second timeout)
                self._persistent_container.stop(timeout=2)
            except (docker.errors.APIError, Exception):
                # If stop fails, force remove will handle it
                pass
            
            try:
                # Force remove to ensure cleanup
                self._persistent_container.remove(force=True)
            except (docker.errors.NotFound, docker.errors.APIError, Exception):
                # Container already removed or in bad state
                pass
            finally:
                self._persistent_container = None
                self._mounted_dir = None

    def execute_command(
        self,
        command: str,
        working_dir: Optional[str] = None
    ) -> Tuple[int, str, str]:
        """
        Execute a command in an isolated Docker container

        Returns:
            (exit_code, stdout, stderr)
        """
        # Try to get or create persistent container
        persistent = self._get_or_create_container(working_dir)
        
        if persistent:
            # Use exec on persistent container (FAST!)
            return self._execute_in_persistent(persistent, command)
        else:
            # Create one-off container (SLOW but clean)
            return self._execute_in_oneoff(command, working_dir)

    def _execute_in_persistent(self, container, command: str) -> Tuple[int, str, str]:
        """
        Execute command in existing persistent container
        
        Args:
            container: Running Docker container
            command: Bash command to execute
            
        Returns:
            (exit_code, stdout, stderr)
        """
        # Wrap command with timeout protection
        wrapped_command = f"timeout {self.config.docker_timeout}s bash -c {repr(command)}"

        try:
            exec_result = container.exec_run(
                wrapped_command,
                demux=True,
                tty=False
            )

        except docker.errors.NotFound:
            # Exec instance or container disappeared; attempt to recreate persistent container
            try:
                self._stop_persistent_container()
                replacement = self._get_or_create_container(self._mounted_dir)
                if replacement:
                    exec_result = replacement.exec_run(
                        wrapped_command,
                        demux=True,
                        tty=False
                    )
                else:
                    # If we couldn't recreate, fall back to one-off execution
                    return self._execute_in_oneoff(command, self._mounted_dir)

            except Exception:
                # Best-effort fallback to one-off container
                return self._execute_in_oneoff(command, self._mounted_dir)

        except docker.errors.APIError:
            # Generic API error during exec - try fallback to one-off execution
            try:
                return self._execute_in_oneoff(command, self._mounted_dir)
            except Exception as e:
                return 1, "", f"Exec API error and fallback failed: {str(e)}"
        except Exception as e:
            return 1, "", f"Exec error: {str(e)}"

        # Normal path: unpack exec_result
        try:
            # `exec_result` can be ExecResult or a tuple depending on SDK
            exit_code = getattr(exec_result, 'exit_code', None)
            output = getattr(exec_result, 'output', None)

            if exit_code is None and isinstance(exec_result, tuple):
                # (exit_code, output)
                exit_code, output = exec_result

            # demux=True -> output is a tuple (stdout_bytes, stderr_bytes)
            if isinstance(output, tuple):
                stdout_bytes, stderr_bytes = output
            else:
                stdout_bytes, stderr_bytes = (output, None)

            stdout = (stdout_bytes or b"").decode("utf-8", errors="ignore")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="ignore")

            # If exit_code is still None, default to 1 on unexpected shape
            if exit_code is None:
                exit_code = 1

            return exit_code, stdout, stderr
        except Exception as e:
            return 1, "", f"Exec unpack error: {str(e)}"

    def _execute_in_oneoff(self, command: str, working_dir: Optional[str] = None) -> Tuple[int, str, str]:
        """
        Execute command in one-off container (old method)
        
        Args:
            command: Bash command to execute
            working_dir: Optional directory to mount
            
        Returns:
            (exit_code, stdout, stderr)
        """
        container = None
        try:
            volumes = {}
            container_workdir = "/workspace"

            if working_dir:
                volumes[os.path.abspath(working_dir)] = {
                    "bind": container_workdir,
                    "mode": "rw"
                }

            wrapped_command = f"timeout {self.config.docker_timeout}s bash -c {repr(command)}"

            container = self.client.containers.run(
                image=self.config.docker_image,
                command=wrapped_command,
                volumes=volumes,
                working_dir=container_workdir,
                detach=True,
                mem_limit=self.config.docker_memory_limit,
                cpu_quota=int(self.config.docker_cpu_limit * 100000),
                network_mode="none",
                remove=False
            )

            result = container.wait(timeout=self.config.docker_timeout + 5)
            exit_code = result.get("StatusCode", 1) if isinstance(result, dict) else 1

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="ignore")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="ignore")

            return exit_code, stdout, stderr

        except Exception as e:
            return 1, "", f"Docker error: {str(e)}"

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    # Log cleanup errors but don't fail
                    pass

    @staticmethod
    def is_docker_available() -> bool:
        """Check Docker availability without creating sandbox"""
        try:
            os.environ.setdefault("DOCKER_HOST", "unix:///var/run/docker.sock")
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False

    def cleanup(self):
        """Remove persistent container and any leftover containers"""
        # Stop persistent container
        self._stop_persistent_container()
        
        # Clean up any leftover containers from previous runs
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"ancestor": self.config.docker_image}
            )

            for c in containers:
                try:
                    c.remove(force=True)
                except docker.errors.APIError as e:
                    # Log cleanup errors but don't fail
                    pass
                except Exception:
                    pass

        except docker.errors.DockerException:
            # Docker connection issue, best effort cleanup
            pass
        except Exception:
            pass
