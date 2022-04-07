import argparse
import glob

from scapy.layers.inet import IP, TCP, UDP
# from scapy.sendrecv import sniff

from scapy.sendrecv import AsyncSniffer

from .flow_session import generate_session_class


def create_sniffer(
    input_file, input_interface, output_mode, output_file, url_model=None
):
    assert (input_file is None) ^ (input_interface is None)

    NewFlowSession = generate_session_class(output_mode, output_file, url_model)

    if input_file is not None:
        #sniff(offline=['/cic/dataset/nsm/log.3.1649256692.pcap'], lfilter=lambda x: IP in x and (TCP in x or UDP in x), prn=lambda x: x.summary(), count=20)
        # sniff(offline=input_file,
        #       filter="ip and (tcp or udp)",
        #       prn=None,
        #       session=NewFlowSession,
        #       store=False,
        #       )
        return AsyncSniffer(
            offline=input_file,
            lfilter=lambda x: IP in x and (TCP in x or UDP in x),
            prn=None,
            session=NewFlowSession,
            store=False,
        )
    else:
        return AsyncSniffer(
            iface=input_interface,
            filter="ip and (tcp or udp)",
            prn=None,
            session=NewFlowSession,
            store=False,
        )


def main():
    parser = argparse.ArgumentParser()

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-i",
        "--interface",
        action="store",
        dest="input_interface",
        help="capture online data from INPUT_INTERFACE",
    )

    input_group.add_argument(
        "-f",
        "--file",
        action="store",
        dest="input_file",
        help="capture offline data from INPUT_FILE pattern",
    )

    input_group.add_argument(
        "-b",
        "--batch",
        action="store",
        dest="batch",
        default=100,
        help="number of files to sniff per session (default=100)",
    )

    output_group = parser.add_mutually_exclusive_group(required=False)
    output_group.add_argument(
        "-c",
        "--csv",
        "--flow",
        action="store_const",
        const="flow",
        dest="output_mode",
        help="output flows as csv",
    )

    url_model = parser.add_mutually_exclusive_group(required=False)
    url_model.add_argument(
        "-u",
        "--url",
        action="store",
        dest="url_model",
        help="URL endpoint for send to Machine Learning Model. e.g http://0.0.0.0:80/prediction",
    )

    parser.add_argument(
        "output",
        help="output file name (in flow mode) or directory (in sequence mode)",
    )

    args = parser.parse_args()
    batch_size = args.batch
    input_interface = args.input_interface
    output_mode = args.output_mode
    output = args.output
    url_model = args.url_model

    if args.input_file is not None:
        files = glob.glob(args.input_file)
        batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
        sniffers = map(lambda i: create_sniffer(i, None, output_mode, output, url_model), batches)

    else:
        sniffers = [create_sniffer(None, input_interface, output_mode, output, url_model)]

    for sniffer in sniffers:
        sniffer.start()
        try:
            sniffer.join()
        except KeyboardInterrupt:
            sniffer.stop()
        finally:
            sniffer.join()


if __name__ == "__main__":
    main()
