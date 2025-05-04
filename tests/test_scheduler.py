import logging
import scheduler

logging.basicConfig(level=logging.INFO)

print('Scheduler configuration:')
sched = scheduler.start_scheduler()

for job in sched.get_jobs():
    print(f'- Job: {job.name}, Trigger: {job.trigger}, Next run: {job.next_run_time}')

# Shut down the scheduler
sched.shutdown()
print('Scheduler test completed successfully')
