import argparse
import glob
import os
import pandas as pd

from cicflowmeter import utils
from cicflowmeter.util.logger import log

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
        # sniff(offline=['/cic/dataset/nsm/log.3.1649256692.pcap'], lfilter=lambda x: IP in x and (TCP in x or UDP in x), prn=lambda x: x.summary(), count=20)
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


def sniff(run) -> bool:
    for tasks in run.sniffer:
        list(map(lambda i: i.start(), tasks))
        try:
            list(map(lambda i: i.join(), tasks))
        except KeyboardInterrupt as e:
            log.error('sniffing tasks interrupted: %s', e)
            list(map(lambda i: i.stop(), tasks))
        finally:
            list(map(lambda i: i.join(), tasks))


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

    batch_group = parser.add_mutually_exclusive_group(required=False)
    batch_group.add_argument(
        "-b",
        "--batch",
        type=int,
        action="store",
        dest="batch",
        default=100,
        help="number of files to sniff per session (default=100)",
    )

    cpu_num_group = parser.add_mutually_exclusive_group(required=False)
    cpu_num_group.add_argument(
        "-cpu",
        "--cpu-num",
        type=int,
        action="store",
        dest="cpu_num",
        default=1,
        help="number of cpus to sniff (default=1)",
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
        help="output directory",
    )

    args = parser.parse_args()
    batch_size = args.batch
    cpu_num = args.cpu_num
    input_interface = args.input_interface
    output_mode = args.output_mode
    output = args.output
    url_model = args.url_model

    if args.input_file is not None:
        input_files = glob.glob(args.input_file)
        file_df = pd.DataFrame(input_files, columns=['input_path'])
        file_df['input_name'] = file_df.apply(lambda i: os.path.split(i.input_path)[-1], axis=1)
        file_df['marked_done_name'] = file_df.apply(lambda i: utils.get_marked_done_file_name(i.input_path), axis=1)
        file_df['marked_done_path'] = file_df.apply(lambda i: os.path.join(output, i.marked_done_name), axis=1)
        file_df['marked_done_existed'] = file_df.apply(lambda i: os.path.exists(i.marked_done_path), axis=1)

        file_df = file_df[file_df['marked_done_existed']].sort_values('input_name')
        file_df['batch'] = file_df.apply(lambda i: i.name // batch_size, axis=1)

        batch_df = file_df.groupby('batch')
        batch_df['output_name'] = batch_df.apply(lambda i: utils.get_output_file_of_batch(i.input_path), axis=1)
        batch_df['sniffer'] = batch_df.apply(lambda i: create_sniffer(
            i.input_path, None, output_mode, i.output_name, url_model), axis=1)
    else:
        sniffers = [create_sniffer(None, input_interface, output_mode, output, url_model)]
        batch_df = pd.DataFrame(sniffers, columns=['sniffer'])

    batch_df['episode'] = batch_df.apply(lambda i: i.name // cpu_num, axis=1)

    log.info('start sniffing: episode=%s', batch_df.count())
    batch_df.apply(lambda i: sniff(i), axis=1)
    log.info('finish sniffing.')


if __name__ == "__main__":
    main()
