"""Coverage for build._gen_dir_for(), the out_root == ROOT branch selector.

Every other test in this suite passes out_root=tmp_path, so the branch that
actually decides where a real (out_root == ROOT) build's generated JSON
lands -- committed spec/_generated for public, gitignored
out/internal/_generated for internal -- was verified only by hand.

Tested directly against the pure path-selection function rather than by
performing a real ROOT-rooted build: that keeps this test from writing into
the actual repository just to prove a path, and still fails if the branch
is broken.
"""
from tools import build


def test_public_at_root_resolves_to_committed_spec_generated():
    assert build._gen_dir_for(False, build.ROOT) == build.SPEC / "_generated"


def test_internal_at_root_resolves_under_gitignored_out_internal():
    got = build._gen_dir_for(True, build.ROOT)
    assert got == build.ROOT / "out" / "internal" / "_generated"
    # The whole point of this branch: a real internal build's generated
    # JSON must land somewhere .gitignore already covers, never at the
    # repo root loose alongside the committed public tables.
    assert "out/internal" in str(got).replace("\\", "/")


def test_public_at_a_non_root_out_dir_resolves_under_it(tmp_path):
    assert build._gen_dir_for(False, tmp_path) == tmp_path / "_generated"


def test_internal_at_a_non_root_out_dir_resolves_under_it(tmp_path):
    assert build._gen_dir_for(True, tmp_path) == tmp_path / "_generated"
