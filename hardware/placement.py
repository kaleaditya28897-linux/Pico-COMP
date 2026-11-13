"""Where the boards sit in the case: shared by mechanical/case.py and keyboard/gen_pcb.py.

Case frame: X right, Y front (0) -> rear/hinge (CASE_D), Z up, mm. PCB frames: origin at the
board's top-left (rear-left) corner, x right, y toward the front of the case.
"""
CASE_W, CASE_D, WALL = 250.0, 140.0, 2.5

KB_W, KB_H = 244.0, 120.0                   # keyboard PCB (keyboard/gen_pcb.py)
KB_X0 = (CASE_W - KB_W) / 2                 # left edge
KB_YTOP = CASE_D - WALL - 1.0               # rear edge

MB_W, MB_H = 152.0, 84.0                    # main PCB (mainboard/gen_pcb.py)
MB_X0 = CASE_W - WALL - 0.5 - MB_W          # right edge 0.5 mm from the wall: ports sit near flush
MB_YTOP = 24.5 + MB_H                       # front edge at y = 24.5, clear of the keyboard's front posts;
                                            # leaves ~26 mm behind the HDMI receptacle (rear rail at y = 135)
                                            # for a slim plug and the cable


def mb_to_case(x, y):
    return MB_X0 + x, MB_YTOP - y


def kb_to_case(x, y):
    return KB_X0 + x, KB_YTOP - y


def case_to_kb(x, y):
    return x - KB_X0, KB_YTOP - y

# keyboard PCB mounting holes (keyboard frame); case.py puts a post under each. Only the front
# header strip has room for screw heads; the rear edge rests on the case's rear rail.
# The middle hole sits left of the mainboard's J11 cable header (case x 108-158).
KB_HOLES = [(3.5, KB_H - 4.0), (90.0, KB_H - 4.0), (KB_W - 3.5, KB_H - 4.0)]
PLATE_R = 4.0                               # key plate corner radius (clears the case's inner corner fillets)
