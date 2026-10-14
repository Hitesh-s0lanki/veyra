# Portrait generation deployment verification — 14 October 2026

The four Modal model apps were redeployed with portrait dimensions. The local hosted API was restarted and `GET /v1/models` listed the portrait presets. One 5-second text-to-video job per model reached `succeeded`; each MP4 was downloaded and checked with FFprobe.

| Model | Resolution | Job ID | Encoded width × height | Duration |
| --- | --- | --- | --- | --- |
| LTX 2.3 | `512p-portrait` | `vid_0943d43ad67dae311c28fdc28cfcce25` | 512 × 768 | 5.04 s |
| Wan 2.2 | `720p-portrait` | `vid_b9c373e7a693fd4bcb585f3722953c51` | 704 × 1280 | 5.04 s |
| HunyuanVideo 1.5 | `480p-portrait` | `vid_6c5a17c0b685814424b5cc723dd47b81` | 480 × 832 | 5.04 s |
| CogVideoX 1.5 | `480p-portrait` | `vid_55d66cc559bdf5f2ac96e9cb42bf61f9` | 480 × 768 | 5.06 s |

All four jobs used the same short kite prompt, a fixed seed, and the default model parameters. This verifies encoded orientation and worker dispatch; it does not assess visual quality or other duration and resolution combinations. Downloaded verification files are in `/tmp/video-portrait-verification/` on the local machine.
