import argparse
import socket
import struct
from datetime import datetime
import time
import os
from random import randint

# create socket object
try:
    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except:
    print("Socket creation error occurred.")

this_host = socket.gethostname()
this_ip_addr = socket.gethostbyname(this_host)

def main():

    parser = argparse.ArgumentParser(description="gets emulator data")

    parser.add_argument('-a', metavar='routetrace_port')
    parser.add_argument('-b', metavar='source_hostname')
    parser.add_argument('-c', metavar='source_port')
    parser.add_argument('-d', metavar='destination_hostname')
    parser.add_argument('-e', metavar='destination_port')
    parser.add_argument('-f', metavar='debug_option')

    args = parser.parse_args()

    routetrace_port = args.a
    source_hostname = args.b
    source_port = args.c
    destination_hostname = args.d
    destination_port = args.e
    debug_option = args.f

    src_ip = socket.gethostbyname(source_hostname)
    dst_ip = socket.gethostbyname(destination_hostname)

    try:
        socket_obj.bind((this_ip_addr, int(routetrace_port)))
    except:
        print("A socket error has occured.")
        return 1

    live_ttl = 0
    while True:
        # construct and send packet
        rt_packet = struct.pack("!cLLHLH", 
                                b'T', 
                                live_ttl, 
                                struct.unpack("!L", socket.inet_aton(this_ip_addr))[0], 
                                int(routetrace_port),
                                struct.unpack("!L", socket.inet_aton(dst_ip))[0],
                                int(destination_port))
        socket_obj.sendto(rt_packet, (src_ip, int(source_port)))

        if debug_option == "1":
            print(f"[   SENT   ] TTL={live_ttl} SRC={this_ip_addr}:{routetrace_port} DST={dst_ip}:{destination_port}")

        # wait for packet to come back
        full_packet, (sender_ip, sender_port) = socket_obj.recvfrom(1024)

        rt_packet = struct.unpack("!cLLHLH", full_packet)
        ttl_in = rt_packet[1]
        rt_src_ip_num = rt_packet[2]
        rt_src_port = rt_packet[3]
        rt_dst_ip_num = rt_packet[4]
        rt_dst_port = rt_packet[5]

        rt_src_ip = socket.inet_ntoa(struct.pack("!L", rt_src_ip_num))
        rt_dst_ip = socket.inet_ntoa(struct.pack("!L", rt_dst_ip_num))

        src_id = f"{rt_src_ip},{rt_src_port}"
        dst_id = f"{rt_dst_ip},{rt_dst_port}"

        if debug_option == "1":
            print(f"[ RECEIVED ] TTL={ttl_in} SRC={rt_src_ip}:{rt_src_port} DST={rt_dst_ip}:{rt_dst_port}")

        print(src_id)

        if(src_id == dst_id):
            break

        live_ttl += 1

        if live_ttl > 30:
            break
    


    return 0


if __name__ == "__main__":
    main()
