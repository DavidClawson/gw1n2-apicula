// GW1N-2 blinky: divide the input clock with a 24-bit counter and drive an LED
// from the top bit. Exercises the carry chain (ALU), flip-flops and IO on the
// GW1N-2 fabric -- enough for the toolchain CI to round-trip the new device.
module blinky (input wire clk, output wire led);
    reg [23:0] cnt = 0;
    always @(posedge clk)
        cnt <= cnt + 1'b1;
    assign led = cnt[23];
endmodule
