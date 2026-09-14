from parser import TaskParser
from datetime import datetime

parser = TaskParser()

test_cases = [
    "Remind me to send a project in 2 days at 5pm",
    "remind me to send an email tomorrow at 4pm",
    "remind me to attend a meeting tomorrow at 5pm",
    "remind me to attend a meeting tomorrow at 5:00pm",
    "remind me to attend a meeting today at 8am",
    "remind me to attend a meeting in 2 days at 6pm",
    "remind me to send an email at 5:30pm",
    "remind me to call john at 3pm",
]

print("Testing time parsing:")
print("=" * 60)

for test in test_cases:
    print(f"\nInput: {test}")
    tasks = parser.parse_task_from_text(test)
    if tasks:
        for task in tasks:
            print(f"  Title: {task.title}")
            print(f"  Deadline: {task.deadline}")
            print(f"  Deadline time: {task.deadline.strftime('%H:%M') if task.deadline else 'None'}")
    else:
        print("  No task parsed")

print("\n" + "=" * 60)
