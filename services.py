import logging
from subprocess import PIPE, Popen, TimeoutExpired

from config import Config, ProgramEntry
from exceptions import BadRequest, ExtractionFailure

logger = logging.getLogger(__name__)


def input_file_has_pdf_extension(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def input_bucket_in_accepted_buckets(uri: str, config: Config) -> bool:
    bucket_name = uri.lower().split("/")[2]
    return config.accepted_buckets is None or bucket_name in config.accepted_buckets


def get_programs(mode: str, engines: list[ProgramEntry]) -> list[ProgramEntry]:
    if mode == "auto":
        return engines
    else:
        program = next((e for e in engines if e.name == mode), None)

        if program is None:
            raise BadRequest
        else:
            return [program]


def get_command_for_program(
    program: ProgramEntry,
    file_in: str,
    file_out: str,
    params: str,
    config: Config,
) -> list[str]:
    from_template = program.template.format(path=program.path, params=params, file_in=file_in, file_out=file_out)
    return config.cgroup_prefix + [part for part in from_template.split() if part]


def convert_file(
    file_path_in: str, mode: str, convert_timeout: int, params: str, config: Config, engines: list[ProgramEntry]
) -> str:
    file_path_out = f"{file_path_in}.txt"
    programs = get_programs(mode, engines)

    for prog in programs:
        cmd = get_command_for_program(prog, file_path_in, file_path_out, params, config)

        try:
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate(timeout=convert_timeout)

            if p.returncode == 0:
                return file_path_out

            error_msg = err.decode("utf-8", errors="replace").strip()
            logger.warning(f"{prog.name} failed with code {p.returncode}: {error_msg}")

        except TimeoutExpired:
            p.kill()
            logger.warning(f"{prog.name} timed out.")
            raise

        except Exception as e:
            logger.error(f"Error extracting text with {prog.name}: {e}")

    # if all modes failed
    logger.error(f"All engines failed to extract text from {file_path_in}")
    raise ExtractionFailure
