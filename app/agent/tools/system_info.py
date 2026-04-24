from __future__ import annotations

from typing import Iterable

import psutil


def _format_bytes(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _disk_lines() -> Iterable[str]:
    lines: list[str] = []
    for p in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(p.mountpoint)
            lines.append(
                f"- {p.device} ({p.mountpoint}): used={_format_bytes(usage.used)}, "
                f"free={_format_bytes(usage.free)}, percent={usage.percent:.1f}%"
            )
        except PermissionError:
            lines.append(f"- {p.device} ({p.mountpoint}): permission denied")
    return lines


async def system_info_tool(info_type: str = "all") -> str:
    mode = info_type.lower().strip()
    sections: list[str] = []

    if mode in {"cpu", "all"}:
        freq = psutil.cpu_freq()
        freq_text = "n/a" if freq is None else f"{freq.current:.1f}MHz"
        sections.append(
            "CPU:\n"
            f"- usage={psutil.cpu_percent(interval=0.4):.1f}%\n"
            f"- cores_logical={psutil.cpu_count(logical=True)}\n"
            f"- cores_physical={psutil.cpu_count(logical=False)}\n"
            f"- frequency={freq_text}"
        )

    if mode in {"ram", "all"}:
        vm = psutil.virtual_memory()
        sections.append(
            "RAM:\n"
            f"- total={_format_bytes(vm.total)}\n"
            f"- used={_format_bytes(vm.used)}\n"
            f"- available={_format_bytes(vm.available)}\n"
            f"- percent={vm.percent:.1f}%"
        )

    if mode in {"disk", "all"}:
        disk_lines = list(_disk_lines())
        sections.append("Disk:\n" + ("\n".join(disk_lines) if disk_lines else "- no partitions"))

    if mode in {"processes", "all"}:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append(
                    (
                        float(info.get("cpu_percent") or 0.0),
                        str(info.get("name") or "unknown"),
                        int(info.get("pid") or 0),
                        float(info.get("memory_percent") or 0.0),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(reverse=True, key=lambda x: x[0])
        top = procs[:10]
        lines = [
            f"- {name} (pid={pid}): cpu={cpu:.1f}%, mem={mem:.2f}%"
            for cpu, name, pid, mem in top
        ]
        sections.append("Processes (top 10 by CPU):\n" + ("\n".join(lines) if lines else "- none"))

    if mode in {"battery", "all"}:
        battery = psutil.sensors_battery()
        if battery is None:
            sections.append("Battery:\n- unavailable")
        else:
            sections.append(f"Battery:\n- percent={battery.percent:.1f}%\n- plugged_in={battery.power_plugged}")

    if mode in {"network", "all"}:
        net = psutil.net_io_counters()
        sections.append(
            "Network:\n"
            f"- bytes_sent={_format_bytes(net.bytes_sent)}\n"
            f"- bytes_recv={_format_bytes(net.bytes_recv)}"
        )

    if not sections:
        return "error: invalid info_type. use cpu|ram|disk|processes|battery|network|all"
    return "\n\n".join(sections)
