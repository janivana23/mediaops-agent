"""Seed demo data: two clients with different budgets, a reference image,
and a handful of jobs that walk through every path the service supports
(auto-delivered, resolution stepdown, approval-required, budget-rejected).

Run with:  python -m app.seed
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from app import config, service
from app.db import init_db, session_scope
from app.models import Client


def _make_reference_image() -> str:
    path = config.OUTPUT_DIR / "seed_reference.png"
    img = Image.new("RGB", (512, 512), (30, 80, 160))
    draw = ImageDraw.Draw(img)
    draw.ellipse([156, 100, 356, 300], fill=(240, 200, 170))  # face
    draw.ellipse([190, 160, 230, 190], fill=(30, 30, 30))  # eye
    draw.ellipse([280, 160, 320, 190], fill=(30, 30, 30))  # eye
    draw.rectangle([120, 320, 392, 512], fill=(20, 90, 60))  # shirt
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return str(path)


def main() -> None:
    init_db()
    reference_path = _make_reference_image()

    with session_scope() as session:
        if session.query(Client).count() > 0:
            print("Already seeded — skipping. Delete mediaops.db to reseed.")
            return

        acme = Client(name="Acme Retail", monthly_budget_cents=60)
        globex = Client(name="Globex Foods", monthly_budget_cents=5000)
        session.add_all([acme, globex])
        session.commit()
        session.refresh(acme)
        session.refresh(globex)

        # 1. Small, cheap job — auto-generates and delivers.
        job1 = service.create_job(
            session,
            client_id=acme.id,
            campaign="Summer Sale",
            prompt="cheerful mascot holding a discount sign",
            kind="image",
            resolution="512x512",
            reference_image_path=reference_path,
        )
        service.run_job(session, job1.id)

        # 2. Requested 1024x1024 but Acme's remaining budget can't cover it —
        #    demonstrates automatic resolution stepdown to 512x512 instead
        #    of failing the job outright.
        job2 = service.create_job(
            session,
            client_id=acme.id,
            campaign="Summer Sale",
            prompt="mascot in front of a storefront banner",
            kind="image",
            resolution="1024x1024",
            reference_image_path=reference_path,
        )
        service.run_job(session, job2.id)

        # 3. Acme's budget is now exhausted — this gets rejected outright.
        job3 = service.create_job(
            session,
            client_id=acme.id,
            campaign="Summer Sale",
            prompt="mascot fireworks finale",
            kind="image",
            resolution="512x512",
            reference_image_path=reference_path,
        )
        service.run_job(session, job3.id)

        # 4. Globex has real budget headroom, but a 2048px hero shot costs
        #    more than the auto-approve threshold — stops at
        #    awaiting_approval for a human to sign off.
        job4 = service.create_job(
            session,
            client_id=globex.id,
            campaign="Harvest Launch",
            prompt="hero shot of the new product line on a farm backdrop",
            kind="image",
            resolution="2048x2048",
            reference_image_path=reference_path,
        )
        service.run_job(session, job4.id)

        # 5. Globex, cheap job — auto-delivers normally.
        job5 = service.create_job(
            session,
            client_id=globex.id,
            campaign="Harvest Launch",
            prompt="close-up of packaging on a wooden table",
            kind="image",
            resolution="1024x1024",
            reference_image_path=reference_path,
        )
        service.run_job(session, job5.id)

        print(f"Seeded clients: acme={acme.id} globex={globex.id}")
        print(f"Jobs: {job1.id}={job1.status} {job2.id}={job2.status} "
              f"{job3.id}={job3.status} {job4.id}={job4.status} {job5.id}={job5.status}")


if __name__ == "__main__":
    main()
