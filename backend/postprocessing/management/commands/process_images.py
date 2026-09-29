import time

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, close_old_connections

from postprocessing.services import claim_job, run_job


class Command(BaseCommand):
    help = 'Process persisted image jobs without contacting model providers.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Consume at most one job and exit.')
        parser.add_argument('--poll-interval', type=float, default=2.0)

    def handle(self, *args, **options):
        if options['poll_interval'] <= 0:
            raise CommandError('poll-interval must be positive.')
        try:
            while True:
                close_old_connections()
                try:
                    job = claim_job()
                    if job:
                        run_job(job)
                except OperationalError:
                    if options['once']:
                        raise
                    time.sleep(options['poll_interval'])
                    continue
                if options['once']:
                    return
                if job is None:
                    time.sleep(options['poll_interval'])
        except KeyboardInterrupt:
            return
