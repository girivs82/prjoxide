# LFCPNX: many registers whose D input is another register's output with no logic in between, so
# the data arrives on the slice's M (bypass) input, from registers placed far apart (a random
# permutation), giving routes that end in "<span> -> m" pips of every kind (for w1:span1w -> m and
# e1:span1w -> m, which the other designs do not exercise). Each register has one of 16 clock
# enables, which keeps synthesis from turning the copy chains into shift-register memories.
import os
import random

N = int(os.environ.get("N_REG", "4000"))
perm = list(range(N))
random.shuffle(perm)
print("module top(input clk, input [15:0] ce, input [7:0] d, output q);")
print("    reg [{}:0] r;".format(N - 1))
for i in range(N):
    src = "r[{}]".format(perm[i]) if i % 64 else "d[{}]".format((i // 64) % 8)
    print("    always @(posedge clk) if (ce[{}]) r[{}] <= {};".format(random.randint(0, 15), i, src))
print("    assign q = ^r;")
print("endmodule")
