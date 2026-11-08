"""GPU smoke test for the Fidetype ROCm environment.

Usage: <venv>\\Scripts\\python.exe tools/env/gpu_smoke.py

The script checks that torch sees the AMD GPU, that GEMM works in fp32
and bf16, that a small training loop runs in bf16 autocast, and that the
fidetype package imports. It exits with code 1 if one check fails.
"""

import platform
import sys
import time

FAILURES: list[str] = []


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    FAILURES.append(msg)


def main() -> int:
    import torch
    import torch.nn as nn

    print(f"python {platform.python_version()} | torch {torch.__version__}")
    print(f"torch.version.hip: {getattr(torch.version, 'hip', None)}")
    avail = torch.cuda.is_available()
    print(f"torch.cuda.is_available(): {avail}")
    if not avail:
        fail("torch.cuda.is_available() is False")
        return 1

    dev = torch.device("cuda")
    props = torch.cuda.get_device_properties(0)
    print(f"device name: {torch.cuda.get_device_name(0)}")
    print(f"arch: {getattr(props, 'gcnArchName', '?')} | "
          f"total mem: {props.total_memory / 2**30:.1f} GiB")
    bf16 = torch.cuda.is_bf16_supported()
    print(f"bf16 supported: {bf16}")
    if not bf16:
        fail("bf16 is not supported")

    # 1. GEMM timings. The fp32 result is compared against the CPU.
    n = 4096
    torch.manual_seed(0)
    for dtype in (torch.float32, torch.bfloat16):
        try:
            a = torch.randn(n, n, device=dev, dtype=dtype)
            b = torch.randn(n, n, device=dev, dtype=dtype)
            t = time.perf_counter()
            c = a @ b
            torch.cuda.synchronize()
            first = time.perf_counter() - t
            iters = 10
            t = time.perf_counter()
            for _ in range(iters):
                c = a @ b
            torch.cuda.synchronize()
            dt = (time.perf_counter() - t) / iters
            tflops = 2 * n**3 / dt / 1e12
            print(f"matmul {n} {str(dtype):15s}: {dt * 1000:7.2f} ms "
                  f"({tflops:5.1f} TFLOPS), first call {first * 1000:.0f} ms")
            if not torch.isfinite(c.float()).all():
                fail(f"matmul {dtype} result has non-finite values")
            if dtype == torch.float32:
                ref = a.cpu() @ b.cpu()
                err = (c.cpu() - ref).abs().max().item()
                scale = ref.abs().max().item()
                rel = err / scale
                print(f"fp32 GPU vs CPU: max abs err {err:.3e}, "
                      f"relative to max {rel:.3e}")
                if rel > 1e-3:
                    fail(f"fp32 GPU result differs from CPU (rel {rel:.3e})")
            del a, b, c
        except Exception as e:  # noqa: BLE001
            fail(f"matmul {dtype}: {e!r}")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    # 2. Ten training steps of a small Conv1d + Transformer in bf16 autocast.
    class Net(nn.Module):
        def __init__(self, c_in: int = 270, d: int = 128, n_cls: int = 10):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(c_in, d, 7, padding=3), nn.GELU(),
                nn.Conv1d(d, d, 5, padding=2, stride=2), nn.GELU())
            layer = nn.TransformerEncoderLayer(
                d, 4, 4 * d, dropout=0.1, batch_first=True)
            self.tf = nn.TransformerEncoder(layer, 4)
            self.head = nn.Linear(d, n_cls)

        def forward(self, x):
            h = self.conv(x).transpose(1, 2)
            return self.head(self.tf(h).mean(1))

    try:
        torch.manual_seed(0)
        model = Net().to(dev)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
        x = torch.randn(64, 270, 100, device=dev)
        y = torch.randint(0, 10, (64,), device=dev)
        lossf = nn.CrossEntropyLoss()
        times, losses = [], []
        for _ in range(10):
            t = time.perf_counter()
            opt.zero_grad()
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss = lossf(model(x), y)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))  # forces a sync
            times.append(time.perf_counter() - t)
        steady = sorted(times[1:])[len(times[1:]) // 2]
        print(f"train bf16 autocast (64 x 270 x 100), 10 steps: "
              f"first step {times[0] * 1000:.0f} ms, "
              f"median of steps 2-10 {steady * 1000:.1f} ms, "
              f"loss {losses[0]:.3f} -> {losses[-1]:.3f}")
        if not all(map(lambda v: v == v and abs(v) != float("inf"), losses)):
            fail("training loss is not finite")
        elif losses[-1] >= losses[0]:
            fail("training loss did not go down")
    except Exception as e:  # noqa: BLE001
        fail(f"training: {e!r}")

    print(f"peak memory allocated (training): "
          f"{torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")

    # 3. The repo package must import.
    try:
        import fidetype
        print(f"import fidetype OK: version {fidetype.__version__} "
              f"from {fidetype.__file__}")
    except Exception as e:  # noqa: BLE001
        fail(f"import fidetype: {e!r}")

    return 1 if FAILURES else 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        fail(f"unexpected error: {e!r}")
        code = 1
    print("SMOKE TEST " + ("PASSED" if code == 0 else
                           f"FAILED ({len(FAILURES)} failures)"))
    sys.exit(code)
