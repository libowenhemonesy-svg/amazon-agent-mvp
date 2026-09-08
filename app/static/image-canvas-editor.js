(function () {
  "use strict";

  const SIZE = 1024;
  const STORAGE_KEY = "amazon-image-canvas-project-v2";
  const state = { stage: null, canvas: null, maskCanvas: null, bufferCanvas: null, project: null, history: [], historyIndex: -1, tool: "select", pointer: null, images: new Map(), sourceUrl: "", viewport: { zoom: 1, x: 0, y: 0 }, spacePressed: false };

  const id = (prefix) => `${prefix}-${crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
  const activeEntity = () => state.project.entities.find((entity) => entity.id === state.project.activeEntityId) || null;
  const rasterEntities = () => state.project.entities.filter((entity) => entity.type === "raster");
  const maskEntities = () => state.project.entities.filter((entity) => entity.type === "inpaint_mask");

  function createProject() { return { version: 2, width: SIZE, height: SIZE, entities: [], activeEntityId: null }; }
  function serialise() { return JSON.stringify(state.project); }
  function restore(value) { state.project = JSON.parse(value); hydrateImages().then(renderAll); }
  function commit() { const value = serialise(); if (state.history[state.historyIndex] === value) return; state.history = state.history.slice(0, state.historyIndex + 1); state.history.push(value); state.historyIndex += 1; try { localStorage.setItem(STORAGE_KEY, value); } catch (_) {} renderLayerPanel(); }
  function undo() { if (state.historyIndex < 1) return; state.historyIndex -= 1; restore(state.history[state.historyIndex]); }
  function redo() { if (state.historyIndex >= state.history.length - 1) return; state.historyIndex += 1; restore(state.history[state.historyIndex]); }

  function attach() {
    if (state.stage || !document.getElementById("image-stage")) return;
    state.stage = document.getElementById("image-stage");
    state.canvas = makeCanvas("canvas-document"); state.maskCanvas = makeCanvas("canvas-mask-overlay"); state.bufferCanvas = makeCanvas("canvas-buffer-overlay");
    state.stage.prepend(state.canvas, state.maskCanvas, state.bufferCanvas);
    const saved = safeProject(); state.project = saved || createProject(); state.history = [serialise()]; state.historyIndex = 0;
    const source = document.getElementById("image-canvas-image"); if (source) { source.style.display = "none"; watchSource(source); }
    bindStage(); bindToolbar(); bindExport(); installLayerPanel(); hydrateImages().then(renderAll);
  }
  function makeCanvas(className) { const canvas = document.createElement("canvas"); canvas.width = SIZE; canvas.height = SIZE; canvas.className = className; return canvas; }
  function safeProject() { try { const project = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); return project?.version === 2 && Array.isArray(project.entities) ? project : null; } catch (_) { return null; } }

  function watchSource(source) {
    const sync = () => { const value = source.getAttribute("src"); if (value && value !== state.sourceUrl) addImageLayer(value); };
    new MutationObserver(sync).observe(source, { attributes: true, attributeFilter: ["src"] }); source.addEventListener("load", sync); sync();
  }
  async function addImageLayer(source) {
    state.sourceUrl = source; const image = await loadImage(source); if (!image) return;
    const entity = { id: id("raster"), type: "raster", name: "产品素材", visible: true, opacity: 1, transform: { x: SIZE / 2, y: SIZE / 2, scale: 1, rotation: 0 }, objects: [{ id: id("image"), type: "image", source, width: image.naturalWidth, height: image.naturalHeight }] };
    state.images.set(source, image); state.project.entities.push(entity); state.project.activeEntityId = entity.id; commit(); renderAll(); document.getElementById("image-empty-canvas")?.setAttribute("hidden", "");
  }
  function loadImage(source) { if (state.images.has(source)) return Promise.resolve(state.images.get(source)); return new Promise((resolve) => { const image = new Image(); image.onload = () => { state.images.set(source, image); resolve(image); }; image.onerror = () => resolve(null); image.src = source; }); }
  async function hydrateImages() { await Promise.all(rasterEntities().flatMap((entity) => entity.objects.filter((object) => object.type === "image").map((object) => loadImage(object.source)))); }

  function bindStage() {
    state.stage.addEventListener("pointerdown", pointerDown); window.addEventListener("pointermove", pointerMove); window.addEventListener("pointerup", pointerUp);
    window.addEventListener("keydown", (event) => { if (event.code === "Space" && !isTextInput(event.target)) { state.spacePressed = true; event.preventDefault(); } if (!event.ctrlKey && !event.metaKey) return; if (event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); } });
    window.addEventListener("keyup", (event) => { if (event.code === "Space") state.spacePressed = false; });
  }
  function bindToolbar() {
    const bar = document.querySelector(".editor-canvasbar"); if (bar && !document.getElementById("canvas-undo")) {
      const undoButton = button("↶", "撤销", undo); undoButton.id = "canvas-undo"; const redoButton = button("↷", "重做", redo); redoButton.id = "canvas-redo";
      const before = bar.querySelector("#image-zoom-out"); bar.insertBefore(undoButton, before); bar.insertBefore(redoButton, before);
    }
    document.querySelectorAll(".canvas-tooltray button").forEach((item) => item.addEventListener("click", () => { state.tool = item.dataset.tool; state.stage.classList.toggle("is-painting", isMaskTool()); }));
  }
  function bindExport() { const old = document.getElementById("image-export"); if (!old) return; const next = old.cloneNode(true); old.replaceWith(next); next.addEventListener("click", exportComposite); }
  function button(text, title, handler) { const item = document.createElement("button"); item.type = "button"; item.textContent = text; item.title = title; item.addEventListener("click", handler); return item; }

  function installLayerPanel() {
    const section = [...document.querySelectorAll(".image-editor-right section")].find((item) => item.textContent.includes("画布图层")); if (!section || document.getElementById("canvas-layer-list")) return;
    const list = document.createElement("div"); list.id = "canvas-layer-list"; section.append(list);
  }
  function renderLayerPanel() {
    const list = document.getElementById("canvas-layer-list"); if (!list) return; list.replaceChildren(); [...state.project.entities].reverse().forEach((entity) => {
      const row = document.createElement("div"); row.className = `canvas-layer-row${entity.id === state.project.activeEntityId ? " is-active" : ""}`;
      const visible = button(entity.visible ? "◉" : "○", "显示/隐藏", () => { entity.visible = !entity.visible; commit(); renderAll(); });
      const name = button(entity.name, "选择图层", () => { state.project.activeEntityId = entity.id; commit(); renderAll(); }); name.className = "canvas-layer-name";
      const up = button("↑", "上移", () => moveEntity(entity.id, 1)); const down = button("↓", "下移", () => moveEntity(entity.id, -1)); const remove = button("×", "删除图层", () => deleteEntity(entity.id)); remove.className = "layer-delete";
      row.append(visible, name, up, down, remove); list.append(row);
    });
  }
  function moveEntity(entityId, direction) { const index = state.project.entities.findIndex((entity) => entity.id === entityId); const target = index + direction; if (target < 0 || target >= state.project.entities.length) return; [state.project.entities[index], state.project.entities[target]] = [state.project.entities[target], state.project.entities[index]]; commit(); renderAll(); }
  function deleteEntity(entityId) { state.project.entities = state.project.entities.filter((entity) => entity.id !== entityId); state.project.activeEntityId = state.project.entities.at(-1)?.id || null; commit(); renderAll(); }

  function isMaskTool() { return state.tool === "mask" || state.tool === "inpaint" || state.tool === "erase"; }
  function point(event) { const rect = state.stage.getBoundingClientRect(); const fit = viewTransform(); return { x: (event.clientX - rect.left - fit.x) / fit.scale, y: (event.clientY - rect.top - fit.y) / fit.scale }; }
  function pointerDown(event) {
    if (event.button === 1 || state.spacePressed) { event.preventDefault(); state.pointer = { kind: "viewport", clientX: event.clientX, clientY: event.clientY, origin: { ...state.viewport } }; state.stage.classList.add("is-panning"); return; }
    if (!state.project.entities.length) return; const p = point(event);
    if (isMaskTool()) { const entity = getOrCreateMaskEntity(); state.pointer = { kind: "stroke", entity, points: [p] }; renderBuffer(); state.stage.setPointerCapture?.(event.pointerId); return; }
    const entity = activeEntity(); if (!entity || entity.type !== "raster") return; state.pointer = { kind: "transform", entity, origin: { ...entity.transform }, point: p };
  }
  function pointerMove(event) { if (!state.pointer) return; if (state.pointer.kind === "viewport") { state.viewport.x = state.pointer.origin.x + event.clientX - state.pointer.clientX; state.viewport.y = state.pointer.origin.y + event.clientY - state.pointer.clientY; renderAll(); return; } const p = point(event); if (state.pointer.kind === "stroke") { state.pointer.points.push(p); renderBuffer(); return; } const { entity, origin, point: start } = state.pointer; entity.transform.x = origin.x + p.x - start.x; entity.transform.y = origin.y + p.y - start.y; renderAll(); }
  function pointerUp() { if (!state.pointer) return; if (state.pointer.kind === "viewport") { state.pointer = null; state.stage.classList.remove("is-panning"); return; } if (state.pointer.kind === "stroke" && state.pointer.points.length > 1) { state.pointer.entity.objects.push({ id: id("stroke"), type: "stroke", points: state.pointer.points, size: 54, erase: state.tool === "erase" }); } state.pointer = null; clearCanvas(state.bufferCanvas); commit(); renderAll(); }
  function getOrCreateMaskEntity() { let entity = activeEntity(); if (entity?.type === "inpaint_mask") return entity; entity = state.project.entities.find((item) => item.type === "inpaint_mask"); if (!entity) { entity = { id: id("mask"), type: "inpaint_mask", name: "局部重绘蒙版", visible: true, opacity: 1, objects: [] }; state.project.entities.push(entity); } state.project.activeEntityId = entity.id; return entity; }

  function viewTransform() { const scale = Math.min(state.stage.clientWidth / SIZE, state.stage.clientHeight / SIZE) * state.viewport.zoom; return { scale, x: (state.stage.clientWidth - SIZE * scale) / 2 + state.viewport.x, y: (state.stage.clientHeight - SIZE * scale) / 2 + state.viewport.y }; }
  function changeViewportZoom(delta) { state.viewport.zoom = Math.max(.25, Math.min(4, state.viewport.zoom + delta)); renderAll(); return state.viewport.zoom; }
  function resetViewport() { state.viewport = { zoom: 1, x: 0, y: 0 }; renderAll(); return state.viewport.zoom; }
  function isTextInput(target) { return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable; }
  function positionCanvases() { const fit = viewTransform(); [state.canvas, state.maskCanvas, state.bufferCanvas].forEach((canvas) => { canvas.style.transform = `translate(${fit.x}px, ${fit.y}px) scale(${fit.scale})`; }); }
  function renderAll() { if (!state.canvas) return; positionCanvases(); const context = clearCanvas(state.canvas); state.project.entities.forEach((entity) => { if (entity.type === "raster" && entity.visible) drawRasterEntity(context, entity); }); renderMasks(); renderLayerPanel(); }
  function drawRasterEntity(context, entity) { context.save(); context.globalAlpha = entity.opacity; context.translate(entity.transform.x, entity.transform.y); context.rotate((entity.transform.rotation * Math.PI) / 180); context.scale(entity.transform.scale, entity.transform.scale); entity.objects.forEach((object) => { if (object.type !== "image") return; const image = state.images.get(object.source); if (!image) return; const ratio = Math.min(SIZE / object.width, SIZE / object.height); context.drawImage(image, -object.width * ratio / 2, -object.height * ratio / 2, object.width * ratio, object.height * ratio); }); context.restore(); }
  function renderMasks() { const context = clearCanvas(state.maskCanvas); maskEntities().filter((entity) => entity.visible).forEach((entity) => { context.save(); context.globalAlpha = .42 * entity.opacity; entity.objects.forEach((object) => drawStroke(context, object, "#ff3b30")); context.restore(); }); }
  function renderBuffer() { const context = clearCanvas(state.bufferCanvas); if (!state.pointer || state.pointer.kind !== "stroke") return; drawStroke(context, { points: state.pointer.points, size: 54 }, state.tool === "erase" ? "#64748b" : "#ff3b30"); }
  function drawStroke(context, stroke, color) { if (stroke.type && stroke.type !== "stroke") return; const points = stroke.points || []; if (points.length < 2) return; context.save(); context.globalCompositeOperation = stroke.erase ? "destination-out" : "source-over"; context.strokeStyle = color; context.lineWidth = stroke.size; context.lineCap = "round"; context.lineJoin = "round"; context.beginPath(); context.moveTo(points[0].x, points[0].y); points.slice(1).forEach((point) => context.lineTo(point.x, point.y)); context.stroke(); context.restore(); }
  function clearCanvas(canvas) { const context = canvas.getContext("2d"); context.clearRect(0, 0, SIZE, SIZE); return context; }

  function composeRaster() { const canvas = makeCanvas("offscreen"); const context = clearCanvas(canvas); rasterEntities().filter((entity) => entity.visible).forEach((entity) => drawRasterEntity(context, entity)); return canvas; }
  function composeMask() { const canvas = makeCanvas("offscreen"); const context = clearCanvas(canvas); maskEntities().filter((entity) => entity.visible).forEach((entity) => entity.objects.forEach((object) => drawStroke(context, object, "#fff"))); return canvas; }
  function exportComposite() { const link = document.createElement("a"); link.download = "amazon-canvas.png"; link.href = composeRaster().toDataURL("image/png"); link.click(); }
  function generationPayload() { return { image: composeRaster().toDataURL("image/png"), mask: composeMask().toDataURL("image/png"), project: JSON.parse(serialise()) }; }

  new MutationObserver(attach).observe(document.body, { childList: true, subtree: true }); attach();
  function setActiveTransform(transform) { const entity = activeEntity(); if (!entity || entity.type !== "raster") return; entity.transform = { ...entity.transform, ...transform }; renderAll(); }
  function toggleActiveLayer() { const entity = activeEntity(); if (!entity) return; entity.visible = !entity.visible; commit(); renderAll(); }
  window.ImageCanvasEditor = { attach, undo, redo, exportComposite, getProject: () => JSON.parse(serialise()), getGenerationPayload: generationPayload, setActiveTransform, toggleActiveLayer, changeViewportZoom, resetViewport };
})();
