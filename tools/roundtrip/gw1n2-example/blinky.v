// GW1N-2 blinky: divide the input clock with a counter and drive an LED from the
// top bit. Exercises a wide counter (ALU/carry chain) + FFs + IO on real GW1N-2.
module blinky (input wire clk, output wire led);
    reg [23:0] cnt = 0;
    always @(posedge clk)
        cnt <= cnt + 1'b1;
    assign led = cnt[23];
endmodule
