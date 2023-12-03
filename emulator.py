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

def readtopology():
    return 0

def createroutes():
    return 0

def forwardpacket():
    return 0

def buildForwardTable():
    return 0

def main():
    parser = argparse.ArgumentParser(description="gets emulator data")

    parser.add_argument('-p', metavar='port')
    parser.add_argument('-f', metavar='filename')

    args = parser.parse_args()

    try:
        socket_obj.bind((this_ip_addr, int(args.p)))
    except:
        print("A socket error has occured.")
        return 1

    socket_obj.setblocking(False)

    while True:
        # recieve packet
        try:
            full_packet, (sender_ip, sender_port) = socket_obj.recvfrom(1024)
        except Exception:
            full_packet = None

        if full_packet:
            # unpack packet information
            header = full_packet[:17]
            header = struct.unpack("!BLHLHI", ip_header)
            data = full_packet[26:]

            priority = ip_header[0]
            src_addr = ip_header[1]
            src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
            src_port = ip_header[2]
            dst_addr = ip_header[3]
            dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
            dst_port = ip_header[4]
            length_udp_and_data = ip_header[5]
            packet_type = udp_header[0]
            seq_num = udp_header[1]
            payload_length = udp_header[2]

            # if (packet_type == b'A'):
            #     print(f"[EMULATOR] Recieved ACK for SEQ_NUM {socket.ntohl(seq_num)}")
            # elif (packet_type == b'D'):
            #     print(f"[EMULATOR] Recieved DATA for SEQ_NUM {socket.ntohl(seq_num)}")
            # elif (packet_type == b'R'):
            #     print(f"[EMULATOR] Recieved REQUEST")


            # not valid address
            if not link_params:
                with open(log, 'a') as lf:
                    lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, No forwarding entry found.\n")
            # add to queue if not full
            else:
                # print("Queue length:", len(queue[priority-1]))
                if (len(queue[priority-1]) >= queue_size):
                    # send all end packets if they don't enter queue
                    if(packet_type == 'E'):
                        # send directly to emulator
                        socket_obj.sendto(full_packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
                    with open(log, 'a') as lf:
                        lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Priority queue {priority} was full.\n")
                #add packet to queue
                else:
                    queue[priority-1].append(full_packet)
        
        if packet:
            # get packet info
            ip_header = packet[:17]
            ip_header = struct.unpack("!BLHLHI", ip_header)
            udp_header = packet[17:26]
            udp_header = struct.unpack("!cII", udp_header)
            data = packet[26:]
            priority = ip_header[0]
            src_addr = ip_header[1]
            src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
            src_port = ip_header[2]
            dst_addr = ip_header[3]
            dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
            dst_port = ip_header[4]
            length_udp_and_data = ip_header[5]
            packet_type = udp_header[0]
            seq_num = udp_header[1]
            payload_length = udp_header[2]

            # get link parameters based on packet info
            send_point = (dst_addr, dst_port)
            link_params = static_forwarding_lookup.get(send_point)

            # if there is no valid link available, remove packet from queue and log event
            if (not link_params):
                queue[priority-1].pop(0)
                with open(log, 'a') as lf:
                    lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Destination not in forwarding table.\n")
            # if the rate permits, proceed to send or drop
            elif (1000*(time.time() - last_send_time) > int(link_params[6])):
                # remove packet from queue
                queue[priority-1].pop(0)
                # send
                if(packet_type == b'E' or randint(1, 100) > int(link_params[7])):
                    socket_obj.sendto(packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
                    # print(f"[EMULATOR] Sent {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
                # drop
                else:
                    with open(log, 'a') as lf:
                        lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, loss event occurred.\n")
                    # print(f"[EMULATOR] Dropped {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
                # log last send time for use with rate
                last_send_time = time.time()

    return 0


if __name__ == "__main__":
    main()
