"use client";

import { useEffect, useRef } from "react";

type SceneKind = "strength" | "nutrition";

export function MotionScene({ kind = "strength" }: { kind?: SceneKind }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!host || motion.matches) return;

    let disposed = false;
    let release: (() => void) | undefined;
    let started = false;

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting || started) return;
      started = true;
      void import("three").then((T) => {
        if (disposed) return;
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("webgl2", { alpha: true, antialias: true });
        if (!context) return;
        const renderer = new T.WebGLRenderer({ canvas, context, alpha: true, antialias: true, powerPreference: "low-power" });
        renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
        renderer.toneMapping = T.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.22;
        const scene = new T.Scene();
        const camera = new T.PerspectiveCamera(34, 1, 0.1, 40);
        camera.position.set(0, 0, 8);
        const object = new T.Group();
        scene.add(object, new T.HemisphereLight(0xffe2cb, 0x38120e, 2.3));

        const key = new T.DirectionalLight(0xffa151, 4.5);
        key.position.set(2, 3, 4);
        const rim = new T.DirectionalLight(0xff4a13, 3.5);
        rim.position.set(-3, 1, -4);
        scene.add(key, rim);

        const orange = new T.MeshStandardMaterial({ color: 0xd94a16, metalness: 0.4, roughness: 0.26 });
        const dark = new T.MeshStandardMaterial({ color: 0x251c19, metalness: 0.48, roughness: 0.32 });
        const bright = new T.MeshStandardMaterial({ color: 0xff8841, metalness: 0.35, roughness: 0.3 });
        const materials = [orange, dark, bright];
        const geometries: import("three").BufferGeometry[] = [];

        function place(geometry: import("three").BufferGeometry, material: import("three").Material, x: number, y = 0, z = 0) {
          const part = new T.Mesh(geometry, material);
          part.position.set(x, y, z);
          object.add(part);
          geometries.push(geometry);
          return part;
        }

        if (kind === "strength") {
          place(new T.CylinderGeometry(0.17, 0.17, 2.9, 24), dark, 0).rotation.z = Math.PI / 2;
          for (const sign of [-1, 1]) {
            place(new T.CylinderGeometry(0.66, 0.66, 0.39, 8), orange, sign * 0.97).rotation.z = Math.PI / 2;
            place(new T.CylinderGeometry(0.74, 0.74, 0.29, 8), dark, sign * 1.26).rotation.z = Math.PI / 2;
            place(new T.CylinderGeometry(0.58, 0.58, 0.24, 8), orange, sign * 1.44).rotation.z = Math.PI / 2;
            place(new T.TorusGeometry(0.35, 0.032, 10, 40), bright, sign * 1.57).rotation.y = Math.PI / 2;
            place(new T.SphereGeometry(0.12, 18, 12), dark, sign * 1.58);
          }
          for (let index = -3; index <= 3; index++) {
            place(new T.TorusGeometry(0.17, 0.017, 8, 24), bright, index * 0.1).rotation.y = Math.PI / 2;
          }
        } else {
          place(new T.SphereGeometry(0.96, 36, 20, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), dark, 0);
          place(new T.TorusGeometry(0.95, 0.06, 12, 50), bright, 0).rotation.x = Math.PI / 2;
          [
            [-0.45, 0.15, -0.26], [0.1, 0.22, -0.35], [0.45, 0.17, -0.13],
            [-0.35, 0.12, 0.35], [0.27, 0.17, 0.31], [-0.04, 0.37, 0.05],
          ].forEach(([x, y, z], index) => {
            place(new T.IcosahedronGeometry(index === 5 ? 0.34 : 0.25, 0), index % 2 ? bright : orange, x, y, z).rotation.z = index;
          });
        }

        const orbitGeometry = new T.TorusGeometry(kind === "strength" ? 1.85 : 1.42, 0.012, 6, 70);
        const orbitMaterial = new T.MeshBasicMaterial({ color: 0xff833c, transparent: true, opacity: 0.38 });
        const orbit = new T.Mesh(orbitGeometry, orbitMaterial);
        const orbitGroup = new T.Group();
        orbitGroup.add(orbit);
        scene.add(orbitGroup);
        const sparkGeometry = new T.SphereGeometry(0.045, 10, 8);
        const spark = new T.Mesh(sparkGeometry, bright);
        orbitGroup.add(spark);
        host.append(canvas);
        host.dataset.ready = "true";

        function resize() {
          if (!host) return;
          const { clientWidth, clientHeight } = host;
          if (!clientHeight || !clientWidth) return;
          camera.aspect = clientWidth / clientHeight;
          camera.position.z = Math.max(7.2, 6.9 / camera.aspect);
          camera.updateProjectionMatrix();
          renderer.setSize(clientWidth, clientHeight, false);
        }

        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(host);
        resize();
        let frame = 0;
        let visible = true;
        let previous = 0;
        const visibility = new IntersectionObserver(([entry]) => {
          visible = entry.isIntersecting;
        });
        visibility.observe(host);
        function draw(time: number) {
          frame = requestAnimationFrame(draw);
          if (!visible || document.hidden || time - previous < 30) return;
          previous = time;
          const t = time / 1000;
          object.rotation.set(kind === "strength" ? 0.32 : 0.43, Math.sin(t * 0.68) * 0.55 - 0.22, kind === "strength" ? -0.48 : -0.18);
          object.position.y = Math.sin(t * 1.45) * 0.09 + (kind === "nutrition" ? 0.24 : 0);
          orbitGroup.rotation.set(0.9, 0.46, -0.35 + t * 0.14);
          const radius = kind === "strength" ? 1.85 : 1.42;
          spark.position.set(Math.cos(t) * radius, Math.sin(t) * radius, 0);
          renderer.render(scene, camera);
        }
        frame = requestAnimationFrame(draw);
        release = () => {
          cancelAnimationFrame(frame);
          resizeObserver.disconnect();
          visibility.disconnect();
          geometries.forEach((geometry) => geometry.dispose());
          materials.forEach((material) => material.dispose());
          orbitGeometry.dispose();
          orbitMaterial.dispose();
          sparkGeometry.dispose();
          renderer.dispose();
          renderer.forceContextLoss();
          canvas.remove();
          delete host.dataset.ready;
        };
      }).catch(() => { /* The decorative fallback remains visible. */ });
    }, { rootMargin: "120px" });

    observer.observe(host);
    function handleMotionChange() {
      if (!motion.matches) return;
      disposed = true;
      release?.();
      release = undefined;
    }
    motion.addEventListener("change", handleMotionChange);
    return () => {
      disposed = true;
      observer.disconnect();
      motion.removeEventListener("change", handleMotionChange);
      release?.();
    };
  }, [kind]);

  return <div className={`motion-scene motion-${kind}`} ref={ref} aria-hidden="true">
    <span className="motion-fallback" />
  </div>;
}

