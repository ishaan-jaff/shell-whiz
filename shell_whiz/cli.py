import asyncio
import subprocess
import sys

import inquirer
import openai
import rich
from rich.markdown import Markdown
from yaspin import yaspin

from shell_whiz.argparse import create_argument_parser
from shell_whiz.config import shell_whiz_config, shell_whiz_update_config
from shell_whiz.console import console
from shell_whiz.constants import (
    INV_CLI_ARGS_EXIT_CODE,
    OPENAI_ERROR_EXIT_CODE,
    SW_ERROR,
    SW_ERROR_EXIT_CODE,
    SW_WAIT_MSG,
    SW_WAIT_MSG_COLOR,
)
from shell_whiz.exceptions import (
    ShellWhizTranslationError,
    ShellWhizWarningError,
    ShellWhizEditError,
)
from shell_whiz.openai import (
    get_explanation_of_shell_command,
    recognize_dangerous_command,
    translate_nl_to_shell_command,
    edit_shell_command,
)


def print_explanation(explanation):
    rich.print(
        " ================== [bold green]Explanation[/] =================="
    )
    console.print(Markdown(explanation))
    print()


def print_command(shell_command):
    rich.print(
        "\n ==================== [bold green]Command[/] ====================\n"
    )

    for line in shell_command.splitlines():
        print(f" {line}")

    print()


async def shell_whiz_ask(prompt):
    first_run = True
    edit_prompt = ""

    try:
        shell_command = translate_nl_to_shell_command(prompt)
    except ShellWhizTranslationError:
        rich.print(f"{SW_ERROR}: Shell Whiz doesn't know how to do this.")
        sys.exit(SW_ERROR_EXIT_CODE)

    while True:
        if first_run:
            first_run = False
        elif edit_prompt != "":
            try:
                shell_command = await edit_shell_command(
                    shell_command, edit_prompt
                )
            except ShellWhizEditError:
                pass

        print_command(shell_command)

        explanation_task = asyncio.create_task(
            get_explanation_of_shell_command(shell_command)
        )

        try:
            is_dangerous, dangerous_consequences = recognize_dangerous_command(
                shell_command
            )
        except ShellWhizWarningError:
            is_dangerous = False

        if is_dangerous:
            rich.print(
                f" [bold red]Warning[/]: [bold yellow]{dangerous_consequences}[/]\n"
            )

        with yaspin(text=SW_WAIT_MSG, color=SW_WAIT_MSG_COLOR):
            explanation = await explanation_task

        print_explanation(explanation)

        edit_prompt = ""

        questions = [
            inquirer.List(
                "action",
                message="Select an action",
                carousel=True,
                choices=[
                    "Run this command",
                    "Revise query",
                    "Edit manually",
                    "Exit",
                ],
            )
        ]

        answers = inquirer.prompt(
            questions, theme=inquirer.themes.GreenPassion()
        )
        choice = answers["action"]
        if choice == "Exit":
            sys.exit()
        elif choice == "Revise query":
            edit_prompt = inquirer.text(message="Revise query")
        elif choice == "Edit manually":
            shell_command = inquirer.text(
                message="Edit command", default=shell_command
            )
        elif choice == "Run this command":
            subprocess.run(shell_command, shell=True)
            return


async def run_ai_assistant(args):
    shell_whiz_config()

    if args.sw_command == "ask":
        shell_command = " ".join(args.prompt).strip()
        if shell_command == "":
            rich.print(f"{SW_ERROR}: Please provide a valid prompt.")
            sys.exit(INV_CLI_ARGS_EXIT_CODE)
        await shell_whiz_ask(shell_command)


async def main():
    args = create_argument_parser().parse_args()

    if args.sw_command == "config":
        shell_whiz_update_config()
    elif args.sw_command == "ask":
        await run_ai_assistant(args)


def run():
    try:
        asyncio.run(main())
    except openai.error.APIError:
        rich.print(
            f"{SW_ERROR}: An error occurred while connecting to the OpenAI API. Please retry your request after a brief wait. The problem is on the side of the OpenAI. Visit https://status.openai.com for more information."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.Timeout:
        rich.print(
            f"{SW_ERROR}: OpenAI API request timed out. Please retry your request after a brief wait."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.APIConnectionError:
        rich.print(
            f"{SW_ERROR}: OpenAI API request failed to connect. Please check your internet connection and try again."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.InvalidRequestError:
        rich.print(
            f"{SW_ERROR}: Your request was malformed or missing some required parameters, such as a token or an input."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.AuthenticationError:
        rich.print(
            f"{SW_ERROR}: You are not authorized to access the OpenAI API. You may have entered the wrong API key. Your API key is invalid, expired or revoked. Please run [bold green]sw config[/] to set up the API key. Visit https://platform.openai.com/account/api-keys to get your API key."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.PermissionError:
        rich.print(
            f"{SW_ERROR}: Your API key or token does not have the required scope or role to perform the requested action. Make sure your API key has the appropriate permissions for the action or model accessed."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.RateLimitError:
        rich.print(
            f"{SW_ERROR}: OpenAI API request exceeded rate limit. If you are on a free plan, please upgrade to a paid plan for a better experience with Shell Whiz. Visit https://platform.openai.com/account/billing/limits for more information."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.ServiceUnavailableError:
        rich.print(
            f"{SW_ERROR}: OpenAI API request failed due to a temporary server-side issue. Please retry your request after a brief wait. The problem is on the side of the OpenAI. Visit https://status.openai.com for more information."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except openai.error.OpenAIError:
        rich.print(
            f"{SW_ERROR}: An unknown error occurred while connecting to the OpenAI API. Please retry your request after a brief wait."
        )
        sys.exit(OPENAI_ERROR_EXIT_CODE)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
