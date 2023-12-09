# cs640-p3

| Packet Type | Packet Structure |
|---|---|
| helloMessage | `\| b'H'(1) \| SRC IP (4) \| SRC PORT (2) \|` |
| LinkStateMessage | `\| b'L'\| BASE IP (4) \| BASE PORT (2) \| SEQ NUM (4) \| TTL (4) \| [Neighbor IP (4) \| Neighbor PORT (2) \| COST (4)] (10 x n) \|` |
| routetrace | `\| b'T'(1) \| TTL (4) \| SRC IP (4) \| SRC PORT (2) \| DST IP (4) \| DST PORT (2) \|` |
