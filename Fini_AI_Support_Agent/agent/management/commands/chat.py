"""Interactive CLI chat with the Paylane support agent."""

from django.core.management.base import BaseCommand

from agent.loop import SupportAgent
from agent.tools.store import MockStore


class Command(BaseCommand):
    help = "Interactive Paylane support agent (Azure OpenAI or deterministic)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=["azure", "deterministic"],
            default="azure",
        )

    def handle(self, *args, **options):
        mode = options["mode"]
        agent = SupportAgent(mode=mode, store=MockStore())
        self.stdout.write(self.style.NOTICE(f"Paylane support agent ({mode}). Type 'quit' to exit."))
        self.stdout.write("Seeded users: alice@paylane.test/4242, bob@paylane.test/1111, …")

        while True:
            try:
                user = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("\nBye.")
                break
            if not user:
                continue
            if user.lower() in {"quit", "exit", "q"}:
                self.stdout.write("Bye.")
                break
            turn = agent.handle_user_message(user)
            self.stdout.write(f"Agent: {turn.assistant_text}")
            if turn.tool_calls:
                tools = ", ".join(
                    t.get("name") or t.get("tool", "?") for t in turn.tool_calls
                )
                self.stdout.write(self.style.NOTICE(f"  (tools: {tools})"))
