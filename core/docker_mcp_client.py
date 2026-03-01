import asyncio
import logging
import uuid
from typing import List, Optional
from core.mcp_client import MCPClient

logger = logging.getLogger("docker_mcp")

class DockerMCPClient(MCPClient):
    """
    Расширенный клиент MCP, который запускает сервер в жестком
    Docker контейнере для предотвращения RCE (Remote Code Execution),
    доступа к сети и атаки на файловую систему хоста.
    """
    def __init__(
        self,
        image_name: str,
        container_args: List[str] = None,
        network_none: bool = True,
        mem_limit: str = "256m",
        cpus: float = 0.5,
        readonly_rootfs: bool = True,
        seccomp_profile: Optional[str] = None,
        userns_mode: Optional[str] = None,
        rootless: bool = False,
    ):
        """
        Инициализирует защищенный MCP-контейнер.

        Args:
            image_name: Имя Docker-образа (например, "mcp-calculator:latest")
            container_args: Аргументы, передаваемые entrypoint-у образа.
            network_none: Если True, отключает любой доступ в интернет.
            mem_limit: Ограничение RAM.
            cpus: Ограничение CPU (0.5 = половина одного ядра).
            readonly_rootfs: Делает файловую систему read-only (защита от записи).
            seccomp_profile: Путь к файлу seccomp-профиля для ограничения системных вызовов.
            userns_mode: Режим пользовательских пространств (например, "host" или "private").
            rootless: Если True, запускает контейнер в режиме rootless.
        """
        self.image_name = image_name
        self.container_args = container_args or []
        self._container_name = f"mcp-{uuid.uuid4().hex[:8]}"

        # Формируем команду docker run
        docker_cmd = ["docker", "run", "-i", "--rm"]

        if network_none:
            docker_cmd.extend(["--network", "none"])

        if readonly_rootfs:
            docker_cmd.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid"])

        docker_cmd.extend(["--memory", mem_limit])
        docker_cmd.extend(["--cpus", str(cpus)])

        # Optional security options
        if seccomp_profile:
            docker_cmd.extend(["--security-opt", f"seccomp={seccomp_profile}"])
        if userns_mode:
            docker_cmd.extend(["--userns", userns_mode])
        if rootless:
            docker_cmd.append("--rootless")

        # Base security opts
        docker_cmd.extend([
            "--security-opt", "no-new-privileges:true",
            "--cap-drop", "ALL"
        ])

        docker_cmd.extend(["--name", self._container_name])
        docker_cmd.append(self.image_name)
        docker_cmd.extend(self.container_args)

        logger.debug(f"Docker command: {' '.join(docker_cmd)}")
        super().__init__(docker_cmd[0], docker_cmd[1:])

    async def connect(self):
        """Переопределенный метод для логирования специфики Docker."""
        logger.info(f"Запуск защищенного MCP-контейнера: {' '.join([self.command] + self.args)}")
        
        # Вызываем стандартный connect из базового класса.
        # Docker `run -i` пробрасывает stdin/stdout нашего процесса прямо
        # в stdin/stdout контейнера, так что MCP протокол будет работать прозрачно!
        await super().connect()

    async def close(self):
        """
        Принудительное убийство контейнера, если он завис или мы завершаем работу.
        """
        # Если базовый close не смог нормально завершить через SIGTERM
        await super().close()
        
        if self._container_name:
            logger.debug(f"Принудительная очистка контейнера: {self._container_name}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "rm", "-f", self._container_name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
            except Exception as e:
                logger.error(f"Не удалось удалить контейнер {self._container_name}: {e}")
