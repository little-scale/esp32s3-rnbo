# RNBO codebox filters and state resources

These 12 original MIT-authored codebox programs exercise exact RNBO class names using documented `@state` construction and `.next` calls. They are RNBO `codebox~`, not GenExpr. Each standalone `.rnbo` file equals its five-box stereo patch's embedded code. No alias, patcher-object, additional method or previous Gen result is inherited.

Delay, comb and allpass use one left filter instance, with the right input copied to the right output. That lane is compared numerically under the **same case tolerance and zero-sign policy**; it is not an independently enforced raw-bit observer qualification. The remaining programs have two independent state instances. Normal constructor defaults and original buffer element types are preserved.

Fixed controls are explicit in each body: delay 2 samples; comb 2-sample-equivalent milliseconds with gain .5/feedforward .5/feedback .25; allpass 3-sample-equivalent milliseconds with gain .5; stable dyadic biquad coefficients; onepole 1000/2000 Hz; onepole_lin alpha .25/.5; averages with windows 8/16 and reset false; rampsmooth up/down 4/8 and 8/4; default positive-edge gatetotrig; thresh low −.25/high .25. Delay uses samples, whereas comb/allpass use milliseconds. The declared decimal delays map to exactly 2/3 samples after the normal Float32 argument and 44,100 Hz conversion.

`reference.py` carries mathematical state across twenty full 256-frame callbacks: zero automatic preparation warm blocks, four compared manual warm callbacks and sixteen timed callbacks. It uses independent filter equations and fresh `math.fsum` windows, rather than the generated running accumulator. The mean/absolute mean/RMS startup divides by available history count before filling the window. Because those initial counts include odd divisors, all averages use the predeclared `2e-6` numerical limit. Other ideal filters and linear ramps also use `2e-6`; integer delay, triggers and hysteresis use zero. Rampsmooth's first step on the target-change sample is an explicit boundary policy. Threshold comparisons include equality at both distinct boundaries. No tolerance is fitted to device output.

Vectors include changing signed dyadic input, held values, zero/sign boundaries, and a final value that differs from the next callback's first value. Gatetotrig also has a cold-versus-continuous first-edge witness. Right source-copy lanes include signed zeros, subnormals and finite extremes. The reference tests cover within-block impulse/delay equations, average availability, causal ramps, edge/equality behavior and continuous callback state. No reset, arbitrary modulation, alternative vector size, one-frame ABI or floating-environment equivalence is claimed.

Actual generated-source resource preflight found these **payload lower bounds**, before allocator/object overhead:

| Program | Preserved default storage | Payload |
| --- | --- | ---: |
| delay | One 65,536-slot Float64 ring | 524,288 bytes |
| comb / allpass | Two 65,536-slot Float64 rings per program | 1,048,576 bytes |
| Each average family | Two 44,101-slot Float64 histories | 705,616 bytes |
| Other programs | No DataRefs | 0 bytes of DataRef payload |

A 1 MiB arena cannot hold the default comb/allpass payload plus overhead. This batch therefore requests an explicit **2 MiB structural module arena ceiling**. Capacity is not measured usage. No delay maximum, default ring, sample type, table or allocation behavior is silently changed.

Catalog models are 600–611. Portable tests are in `tools/test_smoke_rnbo_codebox_filters_reference.py`. Ignored `build/research/rnbo-codebox-filters-smoke-v1` retains original exports/preparations, pre-HIL model/scope metadata history, resource preflight and target results. Generated RNBO C++ remains private. Compiler acceptance, hardware functionality, actual memory and callback timing are separate observations; build wall time is not DSP performance.

The [XIAO hardware run](../../../../evidence/xiao-smoke-rnbo-codebox-filters.json) passes all 12 programs across 122,880 values and twenty continuous callbacks each. All memory/allocation gates pass. Actual comb/allpass arena high-water is 1,048,704 bytes per program, above 1 MiB; five callback costs are queued for CPU review. The copied right lane remains under the common numeric gate.
