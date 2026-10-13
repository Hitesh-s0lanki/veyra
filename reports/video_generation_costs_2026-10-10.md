# LTX-2.3 video generation cost record

Recorded on 10 October 2026. Amounts are USD. Modal credits are dollar-denominated compute credits; this report does not invent a separate application credit unit.

## Supported single-clip durations

This deployment accepts **5, 10, and 20 seconds** for both text-to-video and image-plus-text-to-video at 768×512 and 24 fps. The actual encoded outputs are approximately 5.04, 10.04, and 20.04 seconds. A 30-second single generation is rejected. See `src/config.py` for the frame counts.

## Per-job GPU runtime estimates

The worker records time from the start of generation handling through verified video upload in `video_jobs.inference_seconds`. Each estimate below is `worker runtime × GPU hourly rate / 3600`. Rates came from `modal billing rates --json` on 10 October 2026: H100 **$3.95/hour**, H200 **$4.54/hour**. These are **GPU-only estimates**, not exact charges or a price guarantee. Modal bills container startup, warm idle, CPU and memory separately; S3 storage and transfer are outside Modal.

| Requested length | Job / mode | GPU | Worker seconds | GPU runtime estimate |
| --- | --- | --- | ---: | ---: |
| 5 s | Baseline T2V, `vid_5418787b72134dfb85619f26ed86a633` | H100 | 169.862 | $0.18638 |
| 10 s | Validation I2V, `vid_2c5d75e0be2842069387246755d737fd` | H200 | 142.731 | $0.18000 |
| 10 s | Dream Gold first render, `vid_e7ea05c0861547eaaddb3397d246fc9d` | H200 | 176.552 | $0.22265 |
| 10 s | Dream Gold final render, `vid_8fca9d09ed74418c8ec20dcfecac2e3c` | H200 | 129.541 | $0.16337 |
| 20 s | Validation T2V, `vid_19b12df19ca342168c703449eea0d3ae` | H200 | 110.899 | $0.13986 |

The three observed 10-second H200 runs average **$0.18867 of GPU runtime each**. The 20-second sample happened to cost less than the 10-second samples because execution conditions differed; one run is not a reliable duration price. The source rows are in [video_generation_costs_2026-10-10.csv](video_generation_costs_2026-10-10.csv).

## Dream Gold product video: actual Modal app spend

Producing the delivered video took **two** 10-second generations: the first was a close-up discarded during review, and the second was used for the final product video. Their measured GPU runtime estimates total **$0.38602** ($0.22265 + $0.16337). The final render alone accounts for **$0.16337** of that estimate.

The hourly Modal billing report for **13:00–14:00 UTC** shows the deployed `ltx-23-video` app consuming:

| Resource | Reported cost |
| --- | ---: |
| H200 GPU | $0.64999830 |
| CPU | $0.00845813 |
| Memory | $0.07383766 |
| Network egress | $0.00013679 |
| **Total before credits and allowances** | **$0.73243088** |

The database lists only the two Dream Gold video jobs during that hour. Thus **$0.73243 is the observed app-level spend for the product-video session**, including both attempts, startup/warm-idle GPU time, API/scheduler activity, CPU, memory, and egress. It is **not an exact per-job charge**: Modal's report is hourly by app. Compute excluding egress was **$0.73229409** of potential Modal credit use. The current-month Modal billing summary at report time showed **$2.29 in credits applied across the workspace** and **$0 billed so far**; it does not allocate those credits to specific jobs. External S3 costs are not included.

The billing report was retrieved with `modal billing report --for today --resolution h --show-resources --json`; the monthly summary came from `modal billing summary --for 'this month' --json`. Modal states that reports are before credit and allowance adjustments and are available at hourly or daily granularity. [Modal pricing](https://modal.com/pricing) · [Modal billing documentation](https://modal.com/docs/guide/billing)
