"""Run the 12 conversation eval suite."""

from django.core.management.base import BaseCommand

from eval.runner import run_all


class Command(BaseCommand):
    help = "Run Paylane agent conversations and score pass/fail checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=["deterministic", "azure"],
            default="deterministic",
            help=(
                "deterministic = offline rule-based agent (same tools/policy). "
                "azure = live Azure OpenAI tool-calling."
            ),
        )
        parser.add_argument(
            "--case",
            action="append",
            dest="cases",
            help="Optional case id filter (repeatable).",
        )

    def handle(self, *args, **options):
        report = run_all(mode=options["mode"], case_ids=options["cases"])
        self.stdout.write(self.style.NOTICE(f"Mode: {report['mode']}"))
        self.stdout.write(self.style.SUCCESS(f"Score: {report['score']}"))
        for row in report["results"]:
            status = "PASS" if row["passed"] else "FAIL"
            style = self.style.SUCCESS if row["passed"] else self.style.ERROR
            line = f"  [{status}] {row['case_id']}"
            if row["failures"]:
                line += f" — {', '.join(row['failures'])}"
            self.stdout.write(style(line))
        self.stdout.write(f"Report: transcripts/eval_report.json")
