from __future__ import annotations

from PIL import Image

from app import qa


def test_identity_similarity_is_100_for_identical_image(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (128, 128), (100, 150, 200)).save(path)
    assert qa.identity_similarity(str(path), str(path)) == 100.0


def test_identity_similarity_drops_for_very_different_images(tmp_path):
    # Flat single-colour images are a degenerate case for average-hash:
    # every pixel equals the image mean by definition, so *any* uniform
    # colour hashes identically. Real generator output always has internal
    # structure (gradient + shapes), so exercise that instead — a
    # left/right split vs. a top/bottom split of the same two colours.
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    img_a = Image.new("RGB", (128, 128), (0, 0, 0))
    img_a.paste(Image.new("RGB", (64, 128), (255, 255, 255)), (0, 0))
    img_a.save(a)
    img_b = Image.new("RGB", (128, 128), (0, 0, 0))
    img_b.paste(Image.new("RGB", (128, 64), (255, 255, 255)), (0, 0))
    img_b.save(b)
    assert qa.identity_similarity(str(a), str(b)) <= 60.0


def test_brand_compliance_scores_exact_palette_color_as_100(tmp_path):
    path = tmp_path / "brand.png"
    Image.new("RGB", (64, 64), (31, 111, 235)).save(path)  # #1F6FEB
    assert qa.brand_compliance_score(str(path), ["#1F6FEB"]) == 100.0


def test_brand_compliance_scores_far_color_low(tmp_path):
    path = tmp_path / "offbrand.png"
    Image.new("RGB", (64, 64), (255, 0, 255)).save(path)
    assert qa.brand_compliance_score(str(path), ["#1F6FEB"]) < 70.0


def test_seed_from_reference_is_deterministic(tmp_path):
    path = tmp_path / "ref.png"
    Image.new("RGB", (128, 128), (10, 20, 30)).save(path)
    assert qa.seed_from_reference(str(path), "prompt") == qa.seed_from_reference(str(path), "prompt")


def test_seed_from_prompt_when_no_reference():
    assert qa.seed_from_reference(None, "same prompt") == qa.seed_from_reference(None, "same prompt")
    assert qa.seed_from_reference(None, "prompt a") != qa.seed_from_reference(None, "prompt b")
