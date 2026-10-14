import * as THREE from "three";
import {OrbitControls} from "/viewer-assets/OrbitControls.js";

const host = document.getElementById("viewer-canvas");
const section = document.getElementById("model-viewer");
const status = document.getElementById("viewer-status");
const meta = document.getElementById("viewer-meta");
const orientation = document.getElementById("viewer-orientation");
const gizmoStatus = document.getElementById("gizmo-status");
const gizmoMove = document.getElementById("gizmo-move");
const gizmoRotate = document.getElementById("gizmo-rotate");
const gizmoReference = document.getElementById("gizmo-reference");
const gizmoSnap = document.getElementById("gizmo-snap-origin");
const gizmoReset = document.getElementById("gizmo-reset");
const spatialChecks = document.getElementById("spatial-checks");
const checkExtents = document.getElementById("check-extents");
const checkScale = document.getElementById("check-scale");
const checkWorldZ = document.getElementById("check-world-z");
const checkReference = document.getElementById("check-reference");
const checkProvenance = document.getElementById("check-provenance");
const aerialVisible = document.getElementById("aerial-visible");
const aerialOpacity = document.getElementById("aerial-opacity");
const aerialStatus = document.getElementById("aerial-status");
const analysisLegends = document.getElementById("analysis-legends");
const buttons = [...section.querySelectorAll(".viewer-actions button")];
const toggles = [...section.querySelectorAll("input[data-viewer-layer]")];
const colors = {PH_DESIGN: 0xd7a35d, PH_VISUAL_ONLY: 0xa777b2, PH_FACADES: 0x548093,
  PH_TARGET: 0x52966a, REFERENCE_CONTEXT: 0xb4b9b8, ANALYSIS_SHADOW: 0x526f91,
  ANALYSIS_UTCI: 0xd9683f, ANALYSIS_PILES: 0x4c4037};
const analysisLayers = new Set(["ANALYSIS_SHADOW", "ANALYSIS_UTCI", "ANALYSIS_PILES"]);

function startViewer() {
  const renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0xe9efeb);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x7b8b84, 2.5));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(120, -160, 260);
  scene.add(sun);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10000);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.maxPolarAngle = Math.PI * 0.98;
  const grid = new THREE.GridHelper(600, 30, 0x7c9187, 0xb8c6be);
  grid.rotation.x = Math.PI / 2;
  grid.material.transparent = true;
  grid.material.opacity = 0.42;
  scene.add(grid);
  scene.add(new THREE.AxesHelper(20));
  let model = new THREE.Group();
  scene.add(model);
  const aerial = new THREE.Group();
  aerial.name = "PDOK_AERIAL";
  scene.add(aerial);
  let aerialManifest = null;
  let aerialMesh = null;
  let controller = null;
  let selectedKey = null;
  let loadedKey = null;
  let defaultView = null;
  let contextLost = false;
  let activeDetail = null;
  let gizmoMode = "move";
  let gizmoScale = 1;
  let drag = null;

  const gizmo = new THREE.Group();
  gizmo.name = "PLACEMENT_GIZMO";
  scene.add(gizmo);
  const moveHandles = new THREE.Group();
  const rotateHandles = new THREE.Group();
  gizmo.add(moveHandles, rotateHandles);
  const handleMaterial = color => new THREE.MeshBasicMaterial({color, transparent: true, opacity: 0.9,
    depthTest: false, depthWrite: false, side: THREE.DoubleSide});
  function addMoveHandle(axis, color, rotation, position) {
    const group = new THREE.Group();
    group.userData.handle = axis;
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 10, 10), handleMaterial(color));
    shaft.position.copy(position.clone().multiplyScalar(0.5));
    shaft.rotation.copy(rotation);
    shaft.userData.handle = axis;
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.8, 2.5, 12), handleMaterial(color));
    tip.position.copy(position);
    tip.rotation.copy(rotation);
    tip.userData.handle = axis;
    const hitArea = new THREE.Mesh(new THREE.SphereGeometry(1.6, 8, 6),
      new THREE.MeshBasicMaterial({transparent: true, opacity: 0, depthWrite: false}));
    hitArea.position.copy(position);
    hitArea.userData.handle = axis;
    group.add(shaft, tip, hitArea);
    moveHandles.add(group);
  }
  addMoveHandle("x", 0xc8513a, new THREE.Euler(0, 0, -Math.PI / 2), new THREE.Vector3(10, 0, 0));
  addMoveHandle("y", 0x3b8b62, new THREE.Euler(0, 0, 0), new THREE.Vector3(0, 10, 0));
  const planeHandle = new THREE.Mesh(new THREE.PlaneGeometry(3.5, 3.5), handleMaterial(0xd5a43c));
  planeHandle.position.set(2.1, 2.1, 0.05);
  planeHandle.userData.handle = "xy";
  moveHandles.add(planeHandle);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(9, 0.45, 10, 72), handleMaterial(0xc07832));
  ring.userData.handle = "rotate";
  const ringHitArea = new THREE.Mesh(new THREE.TorusGeometry(9, 1.2, 8, 72),
    new THREE.MeshBasicMaterial({transparent: true, opacity: 0, depthWrite: false}));
  ringHitArea.userData.handle = "rotate";
  rotateHandles.add(ring, ringHitArea);
  const pivotMarker = new THREE.Mesh(new THREE.SphereGeometry(0.7, 12, 8), handleMaterial(0x283f63));
  pivotMarker.userData.handle = "rotate";
  rotateHandles.add(pivotMarker);
  gizmo.traverse(object => { object.renderOrder = 20; });
  gizmo.visible = false;

  const draw = () => {
    updateGizmoScreenData();
    if (!contextLost) renderer.render(scene, camera);
  };
  controls.addEventListener("change", draw);
  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    draw();
  };
  new ResizeObserver(resize).observe(host);

  function dispose(group) {
    group.traverse(object => {
      object.geometry?.dispose();
      if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
      else object.material?.dispose();
    });
  }

  async function loadAerial() {
    try {
      const response = await fetch("/api/site-context", {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const manifest = await response.json();
      const corners = manifest.local_corners_m;
      if (manifest.schema_version !== 1 || manifest.kind !== "visual_aerial"
          || !/^[0-9a-f]{64}$/.test(manifest.manifest_sha256)
          || !corners || !["south_west", "south_east", "north_west", "north_east"]
            .every(name => Array.isArray(corners[name]) && corners[name].length === 3 && corners[name].every(Number.isFinite)))
        throw new Error("ongeldig contextmanifest");
      const texture = await new THREE.TextureLoader().loadAsync(manifest.image_url);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
      const positions = [...corners.south_west, ...corners.south_east, ...corners.north_west, ...corners.north_east];
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 0, 1, 1, 1], 2));
      geometry.setIndex([0, 1, 2, 2, 1, 3]);
      const material = new THREE.MeshBasicMaterial({map: texture, side: THREE.DoubleSide, transparent: true,
        opacity: Number(aerialOpacity.value), depthWrite: true});
      aerialMesh = new THREE.Mesh(geometry, material);
      aerial.add(aerialMesh);
      aerialManifest = manifest;
      aerialVisible.disabled = false;
      aerialOpacity.disabled = false;
      aerial.visible = aerialVisible.checked;
      aerialStatus.textContent = `${manifest.source.attribution} · ${manifest.source.title}. Voorlopig uitgelijnde visuele context; geen plot-, noord- of maaiveldbewijs.`;
      section.dataset.siteContext = manifest.context_id;
      section.dataset.siteContextSha256 = manifest.manifest_sha256;
      draw();
    } catch (error) {
      aerialStatus.textContent = `Luchtfotocontext niet beschikbaar: ${error.message}`;
      aerialVisible.checked = false;
      aerialVisible.disabled = true;
      aerialOpacity.disabled = true;
      delete section.dataset.siteContext;
      delete section.dataset.siteContextSha256;
    }
  }

  function clear(message = "Selecteer een project.", state = "empty") {
    controller?.abort();
    controller = null;
    selectedKey = loadedKey = null;
    scene.remove(model);
    dispose(model);
    model = new THREE.Group();
    scene.add(model);
    defaultView = null;
    activeDetail = null;
    analysisLegends.hidden = true;
    gizmo.visible = false;
    setGizmoEnabled(false);
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = message;
    meta.textContent = "Alleen bekijken. Camerabeweging wijzigt de opgeslagen plaatsing of berekening niet.";
    orientation.textContent = "Geografisch noorden en een juridische plotgrens zijn nog niet geverifieerd.";
    section.dataset.state = state;
    delete section.dataset.run;
    delete section.dataset.triangles;
    delete section.dataset.placementState;
    delete section.dataset.designMatrix;
    delete section.dataset.referenceMatrix;
    resetSpatialChecks();
    draw();
  }

  function applyVisibility() {
    for (const toggle of toggles) {
      const layer = model.getObjectByName(toggle.dataset.viewerLayer);
      if (layer) layer.visible = toggle.checked;
    }
    aerial.visible = Boolean(aerialMesh && aerialVisible.checked);
    draw();
  }
  toggles.forEach(toggle => toggle.addEventListener("change", applyVisibility));
  aerialVisible.addEventListener("change", applyVisibility);
  aerialOpacity.addEventListener("input", () => {
    if (aerialMesh) aerialMesh.material.opacity = Number(aerialOpacity.value);
    draw();
  });

  function bounds(designOnly = false) {
    const box = new THREE.Box3();
    for (const layer of model.children) {
      if (layer.visible && (!designOnly || layer.name === "PH_DESIGN" || layer.name === "PH_VISUAL_ONLY")) box.expandByObject(layer);
    }
    if (!designOnly && aerial.visible && aerialMesh) box.expandByObject(aerial);
    return box.isEmpty() && designOnly ? bounds(false) : box;
  }

  function layerBounds(names) {
    const box = new THREE.Box3();
    model.updateMatrixWorld(true);
    for (const name of names) {
      const layer = model.getObjectByName(name);
      if (layer) box.expandByObject(layer);
    }
    return box;
  }

  function setCheck(element, text, level = "neutral") {
    element.textContent = text;
    element.parentElement.dataset.level = level;
  }

  function resetSpatialChecks(message = "Niet beschikbaar") {
    for (const element of [checkExtents, checkScale, checkWorldZ, checkReference, checkProvenance]) setCheck(element, message);
    spatialChecks.dataset.state = "unavailable";
    for (const name of ["designMinZ", "designMaxZ", "maxDimension", "referenceDistance", "scaleStatus", "zStatus"])
      delete spatialChecks.dataset[name];
  }

  function metric(value) {
    return Number(value).toLocaleString("nl-NL", {minimumFractionDigits: 0, maximumFractionDigits: 2});
  }

  function updateSpatialChecks(item) {
    const design = layerBounds(["PH_DESIGN", "PH_VISUAL_ONLY"]);
    if (design.isEmpty()) { resetSpatialChecks("Geen ontwerpmesh beschikbaar"); return; }
    const size = design.getSize(new THREE.Vector3());
    const maxDimension = Math.max(size.x, size.y, size.z);
    setCheck(checkExtents,
      `X ${metric(design.min.x)}…${metric(design.max.x)} m · Y ${metric(design.min.y)}…${metric(design.max.y)} m · Z ${metric(design.min.z)}…${metric(design.max.z)} m. Omvang ${metric(size.x)} × ${metric(size.y)} × ${metric(size.z)} m.`, "ok");

    let scaleStatus = "ok";
    if (maxDimension < 1) {
      scaleStatus = "too-small";
      setCheck(checkScale, `Waarschuwing: grootste afmeting ${metric(maxDimension)} m is kleiner dan 1 m. Controleer Modeleenheid.`, "warning");
    } else if (maxDimension > 500) {
      scaleStatus = "too-large";
      setCheck(checkScale, `Waarschuwing: grootste afmeting ${metric(maxDimension)} m is groter dan 500 m. Controleer Modeleenheid.`, "warning");
    } else {
      setCheck(checkScale, `Geen schaalwaarschuwing volgens de grenzen <1 m en >500 m (grootste afmeting ${metric(maxDimension)} m).`, "ok");
    }

    const tolerance = 0.05;
    let zStatus;
    if (design.min.z < -tolerance) {
      zStatus = "below";
      setCheck(checkWorldZ, `Waarschuwing: ontwerp loopt ${metric(-design.min.z)} m onder wereld Z=0. Dit is geen maaiveldtoets.`, "warning");
    } else if (design.min.z > tolerance) {
      zStatus = "above";
      setCheck(checkWorldZ, `Onderzijde ligt ${metric(design.min.z)} m boven wereld Z=0. Dit is geen maaiveldtoets.`, "warning");
    } else {
      zStatus = "touching";
      setCheck(checkWorldZ, `Onderzijde ligt binnen ±${metric(tolerance)} m van wereld Z=0. Dit bevestigt geen maaiveld.`, "ok");
    }

    const reference = layerBounds(["PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT"]);
    let referenceDistance = NaN;
    if (reference.isEmpty()) {
      setCheck(checkReference, "Geen referentiemesh beschikbaar; overlap kan niet worden gecontroleerd.", "warning");
    } else {
      const gapX = Math.max(reference.min.x - design.max.x, design.min.x - reference.max.x, 0);
      const gapY = Math.max(reference.min.y - design.max.y, design.min.y - reference.max.y, 0);
      referenceDistance = Math.hypot(gapX, gapY);
      if (referenceDistance === 0) {
        setCheck(checkReference, "Ontwerp-envelope overlapt in XY met de beschikbare analysereferenties. Dit is geen plottoets.", "ok");
      } else {
        setCheck(checkReference, `Waarschuwing: ontwerp-envelope ligt ${metric(referenceDistance)} m buiten de beschikbare referentie-envelope. Dit is geen plottoets.`, "warning");
      }
    }

    const hash = typeof item?.context_sha256 === "string" ? item.context_sha256 : null;
    setCheck(checkProvenance, hash
      ? `Referentiemodel SHA-256 ${hash.slice(0, 12)}…; lokale metercoördinaten. Noord, plot en maaiveld niet goedgekeurd.`
      : "Referentiehash ontbreekt. Noord, plot en maaiveld niet goedgekeurd.", hash ? "ok" : "warning");
    spatialChecks.dataset.state = [scaleStatus !== "ok", zStatus !== "touching", !Number.isFinite(referenceDistance) || referenceDistance > 0]
      .some(Boolean) ? "warning" : "ok";
    spatialChecks.dataset.designMinZ = String(Number(design.min.z.toFixed(6)));
    spatialChecks.dataset.designMaxZ = String(Number(design.max.z.toFixed(6)));
    spatialChecks.dataset.maxDimension = String(Number(maxDimension.toFixed(6)));
    spatialChecks.dataset.referenceDistance = Number.isFinite(referenceDistance) ? String(Number(referenceDistance.toFixed(6))) : "unavailable";
    spatialChecks.dataset.scaleStatus = scaleStatus;
    spatialChecks.dataset.zStatus = zStatus;
  }

  function frame(designOnly, direction = new THREE.Vector3(1, -1.4, 1)) {
    const box = bounds(designOnly);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1);
    const fov = THREE.MathUtils.degToRad(camera.fov);
    const angle = Math.min(fov, 2 * Math.atan(Math.tan(fov / 2) * camera.aspect));
    const distance = radius / Math.sin(angle / 2) * 1.15;
    controls.target.copy(center);
    camera.position.copy(center).add(direction.normalize().multiplyScalar(distance));
    camera.near = Math.max(radius / 1000, 0.01);
    camera.far = Math.max(distance * 100, 10000);
    controls.minDistance = Math.max(radius / 100, 0.1);
    controls.maxDistance = distance * 20;
    camera.updateProjectionMatrix();
    controls.update();
    draw();
  }

  function setPreset(direction) { frame(false, direction); }
  document.getElementById("view-fit-design").addEventListener("click", () => frame(true));
  document.getElementById("view-fit-all").addEventListener("click", () => frame(false));
  document.getElementById("view-reset").addEventListener("click", () => {
    if (!defaultView) return;
    camera.position.copy(defaultView.position);
    controls.target.copy(defaultView.target);
    camera.up.set(0, 0, 1);
    controls.update();
    draw();
  });
  document.getElementById("view-top").addEventListener("click", () => setPreset(new THREE.Vector3(0, 0, 1)));
  document.getElementById("view-front").addEventListener("click", () => setPreset(new THREE.Vector3(0, -1, 0.25)));
  document.getElementById("view-side").addEventListener("click", () => setPreset(new THREE.Vector3(1, 0, 0.25)));

  function createModel(data, kind) {
    if (![1, 2].includes(data.schema_version) || data.units !== "meters" || data.up_axis !== "Z" || !Array.isArray(data.layers)) {
      throw new Error("Onbekend 3D-bestandsformaat; verwacht schema 1 of 2, meters en Z-omhoog.");
    }
    if (kind === "preview" && data.kind !== "placement_preview") throw new Error("Dit bestand is geen plaatsingspreview.");
    const group = new THREE.Group();
    const seen = new Set();
    let triangleCount = 0;
    try {
      for (const layer of data.layers) {
        if (!Object.hasOwn(colors, layer.name) || seen.has(layer.name)
            || (layer.name === "PH_VISUAL_ONLY" && kind !== "preview")
            || (analysisLayers.has(layer.name) && (kind !== "analysis" || data.schema_version !== 2)))
          throw new Error("Onbekende of dubbele modellaag.");
        seen.add(layer.name);
        const {vertices, triangles} = layer;
        if (!Array.isArray(vertices) || !Array.isArray(triangles) || vertices.length % 3 || triangles.length % 3
            || !vertices.every(Number.isFinite)
            || !triangles.every(index => Number.isInteger(index) && index >= 0 && index < vertices.length / 3)) {
          throw new Error("Ongeldige meshgegevens.");
        }
        if (!vertices.length || !triangles.length) continue;
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
        geometry.setIndex(triangles);
        geometry.computeVertexNormals();
        const vertexColors = layer.vertex_colors;
        if (vertexColors !== undefined) {
          if (!["ANALYSIS_SHADOW", "ANALYSIS_UTCI"].includes(layer.name)
              || !Array.isArray(vertexColors) || vertexColors.length !== vertices.length
              || !vertexColors.every(value => Number.isInteger(value) && value >= 0 && value <= 255))
            throw new Error("Ongeldige RGB-vertexkleuren.");
          geometry.setAttribute("color", new THREE.Uint8BufferAttribute(vertexColors, 3, true));
        }
        const layerGroup = new THREE.Group();
        layerGroup.name = layer.name;
        layerGroup.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color: vertexColors === undefined ? colors[layer.name] : 0xffffff, roughness: 0.9,
          metalness: 0, side: THREE.DoubleSide, flatShading: true, vertexColors: vertexColors !== undefined})));
        if (layer.name === "PH_DESIGN" || layer.name === "PH_VISUAL_ONLY") layerGroup.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 25),
          new THREE.LineBasicMaterial({color: 0x785a34, transparent: true, opacity: 0.42})));
        group.add(layerGroup);
        triangleCount += triangles.length / 3;
      }
      return {group, triangleCount};
    } catch (error) {
      dispose(group);
      throw error;
    }
  }

  function interpretedScale(units, declaredScale) {
    if (units === "meters") return 1;
    if (units === "millimeters") return 0.001;
    if (units === "centimeters") return 0.01;
    return units === "file" ? declaredScale : NaN;
  }

  function placementMatrix(placement, scale) {
    const translation = placement?.translation_m;
    const values = [translation?.x, translation?.y, translation?.z, placement?.rotation_z_degrees, scale].map(Number);
    if (!values.every(Number.isFinite) || scale <= 0) return null;
    return new THREE.Matrix4().makeTranslation(values[0], values[1], values[2])
      .multiply(new THREE.Matrix4().makeRotationZ(THREE.MathUtils.degToRad(values[3])))
      .multiply(new THREE.Matrix4().makeScale(scale, scale, scale));
  }

  function applyPlacement(detail) {
    activeDetail = detail;
    for (const name of ["PH_DESIGN", "PH_VISUAL_ONLY"]) {
      const layer = model.getObjectByName(name);
      if (layer) { layer.matrixAutoUpdate = false; layer.matrix.identity(); }
    }
    if (detail.kind !== "preview") {
      section.dataset.placementState = "calculated";
      section.dataset.designMatrix = "identity";
      section.dataset.referenceMatrix = "identity";
      gizmo.visible = false;
      setGizmoEnabled(false);
      updateSpatialChecks(detail.item);
      draw();
      return true;
    }
    const item = detail.item;
    const baseScale = Number(item.model_units?.meters_per_coordinate);
    const coordinateScale = Number(item.model_units?.coordinate_scale);
    const declaredScale = Number.isFinite(coordinateScale) && coordinateScale > 0 ? baseScale / coordinateScale : baseScale;
    const currentScale = interpretedScale(detail.currentPlacement?.model_units, declaredScale);
    const base = placementMatrix(item.placement, baseScale);
    const current = placementMatrix(detail.currentPlacement, currentScale);
    if (!base || !current) {
      status.textContent = "Conceptplaatsing bevat nog geen geldige getallen.";
      resetSpatialChecks("Wacht op geldige conceptgetallen");
      return false;
    }
    const delta = current.multiply(base.clone().invert());
    for (const name of ["PH_DESIGN", "PH_VISUAL_ONLY"]) {
      const layer = model.getObjectByName(name);
      if (layer) layer.matrix.copy(delta);
    }
    section.dataset.placementState = detail.placementState;
    section.dataset.designMatrix = delta.elements.map(value => Number(value.toFixed(6))).join(",");
    section.dataset.referenceMatrix = "identity";
    const label = detail.placementState === "draft" ? "Concept (niet opgeslagen)"
      : detail.placementState === "approved" ? "Goedgekeurde plaatsing" : "Opgeslagen concept";
    const placement = detail.currentPlacement;
    orientation.textContent = `${label}: X ${placement.translation_m.x} m · Y ${placement.translation_m.y} m · Z ${placement.translation_m.z} m · rotatie ${placement.rotation_z_degrees}°. Geografisch noorden/plotgrens nog niet geverifieerd.`;
    status.textContent = `${label} in de plaatsingspreview. Referentiecontext blijft op de geverifieerde analyselocatie.`;
    updateSpatialChecks(item);
    setGizmoEnabled(true);
    const designBox = bounds(true);
    if (!designBox.isEmpty()) gizmoScale = THREE.MathUtils.clamp(designBox.getSize(new THREE.Vector3()).length() / 80, 0.5, 8);
    updateGizmo();
    draw();
    return true;
  }

  function setGizmoEnabled(enabled) {
    for (const control of [gizmoMove, gizmoRotate, gizmoReference, gizmoSnap, gizmoReset]) control.disabled = !enabled;
    gizmo.visible = enabled;
    gizmoStatus.textContent = enabled
      ? "Sleep rood voor X, groen voor Y, het gele vlak voor XY of kies Roteer Z. Wereld (0,0) is geen geverifieerd plotpunt."
      : "Alleen beschikbaar in een voltooide plaatsingspreview. Wereld (0,0) is geen geverifieerd plotpunt.";
  }

  function gizmoPivot() {
    const placement = activeDetail?.currentPlacement;
    if (!placement) return null;
    if (gizmoReference.value === "origin") return new THREE.Vector3(
      Number(placement.translation_m.x), Number(placement.translation_m.y), Number(placement.translation_m.z));
    const box = bounds(true);
    if (box.isEmpty()) return null;
    const center = box.getCenter(new THREE.Vector3());
    center.z = box.min.z;
    return center;
  }

  function updateGizmo() {
    if (!gizmo.visible) return;
    const pivot = gizmoPivot();
    if (!pivot) { gizmo.visible = false; return; }
    gizmo.position.copy(pivot);
    gizmo.scale.setScalar(gizmoScale);
    moveHandles.visible = gizmoMode === "move";
    rotateHandles.visible = gizmoMode === "rotate";
    draw();
  }

  function updateGizmoScreenData() {
    for (const name of ["gizmoOrigin", "gizmoX", "gizmoY", "gizmoRing", "gizmoRingQuarter"]) delete section.dataset[name];
    if (!gizmo.visible) return;
    const rect = renderer.domElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const screen = local => {
      const point = local.multiplyScalar(gizmoScale).add(gizmo.position).project(camera);
      return `${(point.x + 1) * rect.width / 2},${(-point.y + 1) * rect.height / 2}`;
    };
    section.dataset.gizmoOrigin = screen(new THREE.Vector3(0, 0, 0));
    section.dataset.gizmoX = screen(new THREE.Vector3(10, 0, 0));
    section.dataset.gizmoY = screen(new THREE.Vector3(0, 10, 0));
    section.dataset.gizmoRing = screen(new THREE.Vector3(9, 0, 0));
    section.dataset.gizmoRingQuarter = screen(new THREE.Vector3(0, 9, 0));
  }

  function setGizmoMode(mode) {
    gizmoMode = mode;
    gizmoMove.setAttribute("aria-pressed", String(mode === "move"));
    gizmoRotate.setAttribute("aria-pressed", String(mode === "rotate"));
    updateGizmo();
  }
  gizmoMove.addEventListener("click", () => setGizmoMode("move"));
  gizmoRotate.addEventListener("click", () => setGizmoMode("rotate"));
  gizmoReference.addEventListener("change", updateGizmo);

  function emitPlacement(translation, rotation) {
    window.dispatchEvent(new CustomEvent("parkhaven-gizmo-placement", {detail: {
      translation_m: {x: Number(translation.x.toFixed(1)), y: Number(translation.y.toFixed(1)),
        z: Number(translation.z.toFixed(1))},
      rotation_z_degrees: Number((((rotation % 360) + 360) % 360).toFixed(1)),
    }}));
  }

  gizmoSnap.addEventListener("click", () => {
    const pivot = gizmoPivot(), placement = activeDetail?.currentPlacement;
    if (!pivot || !placement) return;
    const translation = new THREE.Vector3(Number(placement.translation_m.x) - pivot.x,
      Number(placement.translation_m.y) - pivot.y, Number(placement.translation_m.z));
    emitPlacement(translation, Number(placement.rotation_z_degrees));
  });

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1));
  function ray(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.ray;
  }
  function planePoint(event, z, target = new THREE.Vector3()) {
    dragPlane.constant = -z;
    return ray(event).intersectPlane(dragPlane, target);
  }
  renderer.domElement.addEventListener("pointerdown", event => {
    if (!gizmo.visible || event.button !== 0) return;
    ray(event);
    const hit = raycaster.intersectObject(gizmo, true).find(item => item.object.userData.handle);
    section.dataset.gizmoHit = hit?.object.userData.handle || "none";
    if (!hit) return;
    const pivot = gizmoPivot(), placement = activeDetail.currentPlacement;
    if (!pivot) return;
    const startPoint = planePoint(event, pivot.z);
    if (!startPoint) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    renderer.domElement.setPointerCapture(event.pointerId);
    controls.enabled = false;
    drag = {pointerId: event.pointerId, handle: hit.object.userData.handle, pivot, startPoint: startPoint.clone(),
      translation: new THREE.Vector3(Number(placement.translation_m.x), Number(placement.translation_m.y), Number(placement.translation_m.z)),
      rotation: Number(placement.rotation_z_degrees),
      pointerAngle: Math.atan2(startPoint.y - pivot.y, startPoint.x - pivot.x)};
  }, true);
  renderer.domElement.addEventListener("pointermove", event => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const point = planePoint(event, drag.pivot.z);
    if (!point) return;
    if (drag.handle === "rotate") {
      const angle = Math.atan2(point.y - drag.pivot.y, point.x - drag.pivot.x);
      const delta = Math.atan2(Math.sin(angle - drag.pointerAngle), Math.cos(angle - drag.pointerAngle));
      const offset = drag.translation.clone().sub(drag.pivot).applyAxisAngle(new THREE.Vector3(0, 0, 1), delta);
      emitPlacement(drag.pivot.clone().add(offset), drag.rotation + THREE.MathUtils.radToDeg(delta));
    } else {
      const delta = point.sub(drag.startPoint);
      if (drag.handle === "x") delta.y = 0;
      if (drag.handle === "y") delta.x = 0;
      emitPlacement(drag.translation.clone().add(delta), drag.rotation);
    }
  }, true);
  const endDrag = event => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag = null;
    controls.enabled = true;
    if (renderer.domElement.hasPointerCapture(event.pointerId)) renderer.domElement.releasePointerCapture(event.pointerId);
  };
  renderer.domElement.addEventListener("pointerup", endDrag, true);
  renderer.domElement.addEventListener("pointercancel", endDrag, true);

  function controlledCamera(box, direction, topView = false) {
    const captureCamera = new THREE.PerspectiveCamera(40, 768 / 512, 0.1, 10000);
    const center = box.getCenter(new THREE.Vector3());
    const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1);
    const fov = THREE.MathUtils.degToRad(captureCamera.fov);
    const angle = Math.min(fov, 2 * Math.atan(Math.tan(fov / 2) * captureCamera.aspect));
    const distance = radius / Math.sin(angle / 2) * 1.15;
    captureCamera.up.set(0, topView ? 1 : 0, topView ? 0 : 1);
    captureCamera.position.copy(center).add(direction.clone().normalize().multiplyScalar(distance));
    captureCamera.near = Math.max(radius / 1000, 0.01);
    captureCamera.far = Math.max(distance * 100, 10000);
    captureCamera.lookAt(center);
    captureCamera.updateProjectionMatrix();
    captureCamera.updateMatrixWorld(true);
    return {camera: captureCamera, target: center};
  }

  function referenceDirection(layerName, designCenter) {
    const reference = layerBounds([layerName]);
    if (reference.isEmpty()) throw new Error(`Vereiste referentielaag ${layerName} ontbreekt voor gecontroleerde captures.`);
    const direction = reference.getCenter(new THREE.Vector3()).sub(designCenter);
    direction.z = Math.max(Math.abs(direction.x) + Math.abs(direction.y), 1) * 0.25;
    if (Math.hypot(direction.x, direction.y) < 0.001)
      throw new Error(`Referentielaag ${layerName} levert geen bruikbare camerazijde.`);
    return direction;
  }

  function captureViews(request) {
    if (activeDetail?.kind !== "analysis" || activeDetail.evidenceId !== request.runId || loadedKey !== `analysis/${request.projectId}/${request.runId}`)
      throw new Error("Selecteer en laad eerst de onveranderde laatste analyse.");
    const design = layerBounds(["PH_DESIGN"]);
    const all = layerBounds(["PH_DESIGN", "PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT",
      "ANALYSIS_SHADOW", "ANALYSIS_UTCI", "ANALYSIS_PILES"]);
    if (!aerialManifest || !aerialMesh) throw new Error("De vaste PDOK-luchtfotocontext is nog niet geladen.");
    all.expandByObject(aerial);
    if (design.isEmpty() || all.isEmpty()) throw new Error("De runscene bevat onvoldoende geometrie voor modelbeelden.");
    const designCenter = design.getCenter(new THREE.Vector3());
    const captureBox = layerBounds(["PH_DESIGN", "ANALYSIS_SHADOW", "ANALYSIS_UTCI", "ANALYSIS_PILES"]);
    const captureSize = captureBox.getSize(new THREE.Vector3());
    captureBox.expandByScalar(Math.max(captureSize.x, captureSize.y, captureSize.z) * 0.12);
    const definitions = [
      {id: "top", box: captureBox, direction: new THREE.Vector3(0, 0, 1), top: true},
      {id: "overview", box: captureBox, direction: new THREE.Vector3(1, -1.4, 1)},
      {id: "facade-side", box: captureBox, direction: referenceDirection("PH_FACADES", designCenter)},
      {id: "park-side", box: captureBox, direction: referenceDirection("PH_TARGET", designCenter)},
    ];
    const visibleLayers = [...model.children.filter(layer => layer.children.length > 0).map(layer => layer.name), "PDOK_AERIAL"].sort();
    const visibility = model.children.map(layer => [layer, layer.visible]);
    const aerialWasVisible = aerial.visible;
    const gizmoWasVisible = gizmo.visible;
    const captureRenderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
    captureRenderer.setPixelRatio(1);
    captureRenderer.setSize(768, 512, false);
    captureRenderer.setClearColor(0xe9efeb);
    try {
      model.children.forEach(layer => { layer.visible = layer.children.length > 0; });
      aerial.visible = true;
      gizmo.visible = false;
      scene.updateMatrixWorld(true);
      return definitions.map(definition => {
        const controlled = controlledCamera(definition.box, definition.direction, definition.top);
        captureRenderer.render(scene, controlled.camera);
        return {
          id: definition.id,
          image_data_url: captureRenderer.domElement.toDataURL("image/png"),
          width: 768,
          height: 512,
          projection: "perspective",
          fov_degrees: controlled.camera.fov,
          camera_position: controlled.camera.position.toArray(),
          camera_target: controlled.target.toArray(),
          camera_up: controlled.camera.up.toArray(),
          visible_layers: visibleLayers,
        };
      });
    } finally {
      visibility.forEach(([layer, visible]) => { layer.visible = visible; });
      aerial.visible = aerialWasVisible;
      gizmo.visible = gizmoWasVisible;
      captureRenderer.dispose();
      captureRenderer.forceContextLoss();
      draw();
    }
  }

  window.addEventListener("parkhaven-viewer-capture-request", event => {
    const request = event.detail;
    try {
      const views = captureViews(request);
      window.dispatchEvent(new CustomEvent("parkhaven-viewer-capture-result", {detail: {
        requestId: request.requestId, views, siteContextSha256: aerialManifest.manifest_sha256,
      }}));
    } catch (error) {
      window.dispatchEvent(new CustomEvent("parkhaven-viewer-capture-result", {detail: {
        requestId: request?.requestId, error: error.message || "Modelbeelden konden niet worden gemaakt.",
      }}));
    }
  });

  async function show(detail) {
    if (!detail?.projectId) { clear(); return; }
    const {projectId, evidenceId, endpoint, item, kind} = detail;
    if (!evidenceId || !item) {
      clear(kind === "preview" ? "Maak een plaatsingspreview om het ontwerp vóór analyse te controleren."
        : "Er is nog geen berekende analyse om te tonen.");
      return;
    }
    const key = `${kind}/${projectId}/${evidenceId}`;
    selectedKey = key;
    if (item.status !== "completed") {
      clear(kind === "preview" ? "De plaatsingspreview is nog niet beschikbaar." : "3D-evidence is beschikbaar na een voltooide analyse.");
      return;
    }
    if (!item.scene_available) { clear(kind === "preview" ? "Deze preview bevat geen 3D-scene." : "Deze voltooide run bevat geen 3D-scene.", "error"); return; }
    if (loadedKey === key) { applyPlacement(detail); return; }
    controller?.abort();
    const request = new AbortController();
    controller = request;
    section.dataset.state = "loading";
    status.textContent = kind === "preview" ? "3D-plaatsingspreview laden…" : "3D-scene van de voltooide run laden…";
    const timeout = setTimeout(() => request.abort(), 10000);
    try {
      const response = await fetch(endpoint, {cache: "no-store", signal: request.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== controller || selectedKey !== key) return;
      const next = createModel(data, kind);
      scene.remove(model);
      dispose(model);
      model = next.group;
      scene.add(model);
      analysisLegends.hidden = !model.children.some(layer => analysisLayers.has(layer.name));
      applyVisibility();
      loadedKey = key;
      section.dataset.state = "ready";
      section.dataset.run = evidenceId;
      section.dataset.triangles = String(next.triangleCount);
      buttons.forEach(button => { button.disabled = model.children.length === 0; });
      applyPlacement(detail);
      frame(true);
      defaultView = {position: camera.position.clone(), target: controls.target.clone()};
      const size = item.model_units?.physical_size_m;
      const placement = item.placement;
      const dimensions = Array.isArray(size) ? ` · ontwerp ${size.map(value => Number(value).toLocaleString("nl-NL", {maximumFractionDigits: 2})).join(" × ")} m` : "";
      meta.textContent = `${kind === "preview" ? "Preview" : "Run"} ${evidenceId} · ${next.triangleCount.toLocaleString("nl-NL")} driehoeken${dimensions} · scene in meters, Z-omhoog.`;
      if (kind === "analysis") {
        orientation.textContent = placement
          ? `Berekende plaatsing: X ${placement.translation_m.x} m · Y ${placement.translation_m.y} m · Z ${placement.translation_m.z} m · rotatie ${placement.rotation_z_degrees}°. Geografisch noorden/plotgrens nog niet geverifieerd.`
          : "Plaatsingsmetadata ontbreekt. Geografisch noorden/plotgrens nog niet geverifieerd.";
        status.textContent = model.children.length ? "3D-evidence van de voltooide run geladen." : "De scene bevat geen zichtbare meshgeometrie.";
      } else applyPlacement(detail);
    } catch (error) {
      if (request === controller && error.name !== "AbortError") clear(`3D-scene kon niet worden geladen: ${error.message}`, "error");
    } finally {
      clearTimeout(timeout);
      if (request === controller) controller = null;
    }
  }

  window.addEventListener("parkhaven-viewer-run", event => show(event.detail));
  renderer.domElement.addEventListener("webglcontextlost", event => {
    event.preventDefault();
    contextLost = true;
    section.dataset.state = "error";
    status.textContent = "3D-weergave onderbroken (WebGL). De berekeningsresultaten blijven beschikbaar.";
  });
  renderer.domElement.addEventListener("webglcontextrestored", () => { contextLost = false; draw(); });
  resize();
  loadAerial();
  clear();
}

try { startViewer(); }
catch (error) {
  section.dataset.state = "error";
  status.textContent = "3D-weergave niet beschikbaar: WebGL kon niet worden gestart. De berekeningsresultaten blijven beschikbaar.";
}
