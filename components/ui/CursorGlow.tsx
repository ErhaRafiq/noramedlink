"use client";

import { useEffect, useRef } from "react";

export function CursorGlow() {
  const glowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const glow = glowRef.current;
    if (!glow || window.matchMedia("(pointer: coarse)").matches) {
      return;
    }
    const glowElement = glow;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 2;
    let currentX = targetX;
    let currentY = targetY;
    let frameId = 0;

    function move(event: PointerEvent) {
      targetX = event.clientX;
      targetY = event.clientY;
      glowElement.style.opacity = "1";
    }

    function hide() {
      glowElement.style.opacity = "0";
    }

    function animate() {
      currentX += (targetX - currentX) * 0.14;
      currentY += (targetY - currentY) * 0.14;
      glowElement.style.transform = `translate3d(${currentX - 144}px, ${currentY - 144}px, 0)`;
      frameId = window.requestAnimationFrame(animate);
    }

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerleave", hide);
    animate();

    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerleave", hide);
      window.cancelAnimationFrame(frameId);
    };
  }, []);

  return <div ref={glowRef} className="cursor-glow" aria-hidden="true" />;
}
