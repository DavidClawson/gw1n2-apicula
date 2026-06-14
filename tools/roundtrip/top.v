// Minimal round-trip test for GW1N-2: registered AND gate.
// Exercises LUT (a & b), DFF (posedge clk), IO buffers, and inter-tile routing.
module top (input wire clk, input wire a, input wire b, output wire q);
    reg r;
    always @(posedge clk)
        r <= a & b;
    assign q = r;
endmodule
