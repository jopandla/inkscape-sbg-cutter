import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sbgcut"))
import sbg_protocol as P

# BD:9 pairs captured live (x -> y)
BD9 = [(12345, 1116696875), (6514388372 & 0xffffffff, 3335834112),
       (9878385181 & 0xffffffff, 2384153743), (7457383991, 4262060837)]
# BD:12 pairs captured live (challenge -> answer)
BD12 = [(363492893, 2068321915), (4272747167, 3058602489), (1106888792, 1205421250),
        (761919855, 2760479657), (3352377459, 2921419797), (3163491442, 4100663320)]

def test_bd9():
    for x, y in BD9:
        assert P.bd9_response(x) == y, (x, y, P.bd9_response(x))

def test_bd12():
    for c, z in BD12:
        assert P.bd12_answer(c) == z, (c, z, P.bd12_answer(c))

def test_square_matches_known_good():
    # the exact job string that cut a 10x10mm square at (10,10) on the real machine
    expected = ("IN IN WSJP=2026743391 U0,0 D0,0 D0,10 U0,0 D640,0 "
                "U100,100 D300,100 D300,300 D100,300 D100,100 U0,0 @ ")
    square = [[(0.0,0.0),(10.0,0.0),(10.0,10.0),(0.0,10.0),(0.0,0.0)]]
    job = P.build_job(square, origin_mm=(10.0,10.0))
    assert job == expected, "\n got: %r\nwant: %r" % (job, expected)

if __name__ == "__main__":
    test_bd9(); test_bd12(); test_square_matches_known_good()
    print("all protocol tests PASS")
