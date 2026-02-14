"""CLI tools for NitROS - topic inspection and debugging."""

import argparse
import collections
import pprint
import sys
import time

from .discovery import list_all_services


def cmd_topic_list(args):
    """List all active topics on the network."""
    print(f"Scanning for topics ({args.timeout}s)...")
    topics = list_all_services(timeout=args.timeout)

    if not topics:
        print("No active topics found.")
        return

    # Calculate column widths
    max_name = max(len(t) for t in topics)
    max_name = max(max_name, 5)  # min width for "Topic"

    print(f"\n{'Topic':<{max_name}}  Publishers")
    print(f"{'-' * max_name}  ----------")
    for topic, publishers in sorted(topics.items()):
        print(f"{topic:<{max_name}}  {len(publishers)}")


def cmd_topic_echo(args):
    """Subscribe to a topic and print messages."""
    from .subscriber import Subscriber

    def on_message(msg):
        if isinstance(msg, dict):
            pprint.pprint(msg)
        else:
            # numpy arrays, etc.
            print(repr(msg))

    print(f"Listening on '{args.topic}' (Ctrl+C to stop)...")
    sub = Subscriber(args.topic, on_message)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()


def cmd_topic_hz(args):
    """Measure the publish rate of a topic."""
    from .subscriber import Subscriber

    timestamps = collections.deque(maxlen=args.window)

    def on_message(msg):
        timestamps.append(time.monotonic())

    print(f"Measuring rate on '{args.topic}' (Ctrl+C to stop)...")
    sub = Subscriber(args.topic, on_message)

    try:
        while True:
            time.sleep(1.0)
            if len(timestamps) < 2:
                print("  no messages yet")
                continue
            dt = timestamps[-1] - timestamps[0]
            if dt > 0:
                hz = (len(timestamps) - 1) / dt
                print(f"  average rate: {hz:.1f} Hz ({len(timestamps)} msgs in {dt:.2f}s)")
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()


def cmd_topic_info(args):
    """Show detailed information about a topic."""
    print(f"Scanning for '{args.topic}' ({args.timeout}s)...")
    topics = list_all_services(timeout=args.timeout)

    publishers = topics.get(args.topic)
    if not publishers:
        print(f"Topic '{args.topic}' not found.")
        return

    print(f"\nTopic: {args.topic}")
    print(f"Publishers: {len(publishers)}")
    for i, pub in enumerate(publishers):
        compression = pub["compression"] or "none"
        print(f"  [{i}] {pub['host']}:{pub['port']}  compression={compression}")


def main():
    parser = argparse.ArgumentParser(prog="nitros", description="NitROS CLI tools")
    sub = parser.add_subparsers(dest="command")

    # nitros topic ...
    topic_parser = sub.add_parser("topic", help="Topic inspection tools")
    topic_sub = topic_parser.add_subparsers(dest="topic_command")

    # nitros topic list
    list_parser = topic_sub.add_parser("list", help="List active topics")
    list_parser.add_argument("-t", "--timeout", type=float, default=2.0,
                             help="Scan duration in seconds (default: 2)")

    # nitros topic echo <name>
    echo_parser = topic_sub.add_parser("echo", help="Print messages on a topic")
    echo_parser.add_argument("topic", help="Topic name")

    # nitros topic hz <name>
    hz_parser = topic_sub.add_parser("hz", help="Measure topic publish rate")
    hz_parser.add_argument("topic", help="Topic name")
    hz_parser.add_argument("-w", "--window", type=int, default=100,
                           help="Window size for rate calculation (default: 100)")

    # nitros topic info <name>
    info_parser = topic_sub.add_parser("info", help="Show topic details")
    info_parser.add_argument("topic", help="Topic name")
    info_parser.add_argument("-t", "--timeout", type=float, default=2.0,
                             help="Scan duration in seconds (default: 2)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "topic":
        if args.topic_command is None:
            topic_parser.print_help()
            return

        handlers = {
            "list": cmd_topic_list,
            "echo": cmd_topic_echo,
            "hz": cmd_topic_hz,
            "info": cmd_topic_info,
        }
        handlers[args.topic_command](args)


if __name__ == "__main__":
    main()
