// ============================================================
// DADOS DAS VERSÕES DA ONTOLOGIA ESCOLAR
// ============================================================
const ontologyVersions = [
    {
        id: 'v1', name: 'v1 - Versão Inicial',
        desc: 'Estrutura básica com classes fundamentais do ambiente escolar.',
        date: '2024-01-15',
        classes: [
            { id: 'Escola', label: 'Escola' },
            { id: 'Aluno', label: 'Aluno' },
            { id: 'Professor', label: 'Professor' },
            { id: 'Turma', label: 'Turma' }
        ],
        relations: [
            { subject: 'Aluno', predicate: 'estudaEm', object: 'Turma' },
            { subject: 'Professor', predicate: 'lecionaEm', object: 'Turma' },
            { subject: 'Turma', predicate: 'pertenceA', object: 'Escola' }
        ]
    },
    {
        id: 'v2', name: 'v2 - Adição de Disciplinas',
        desc: 'Inclusão de disciplinas e suas relações com professores e turmas.',
        date: '2024-03-02',
        classes: [
            { id: 'Escola', label: 'Escola' },
            { id: 'Aluno', label: 'Aluno' },
            { id: 'Professor', label: 'Professor' },
            { id: 'Turma', label: 'Turma' },
            { id: 'Disciplina', label: 'Disciplina' }
        ],
        relations: [
            { subject: 'Aluno', predicate: 'estudaEm', object: 'Turma' },
            { subject: 'Professor', predicate: 'lecionaEm', object: 'Turma' },
            { subject: 'Turma', predicate: 'pertenceA', object: 'Escola' },
            { subject: 'Professor', predicate: 'ministra', object: 'Disciplina' },
            { subject: 'Disciplina', predicate: 'fazParteDe', object: 'Turma' }
        ]
    },
    {
        id: 'v3', name: 'v3 - Avaliações e Notas',
        desc: 'Introdução de avaliações, notas e conceitos de desempenho.',
        date: '2024-05-10',
        classes: [
            { id: 'Escola', label: 'Escola' },
            { id: 'Aluno', label: 'Aluno' },
            { id: 'Professor', label: 'Professor' },
            { id: 'Turma', label: 'Turma' },
            { id: 'Disciplina', label: 'Disciplina' },
            { id: 'Avaliacao', label: 'Avaliação' },
            { id: 'Nota', label: 'Nota' }
        ],
        relations: [
            { subject: 'Aluno', predicate: 'estudaEm', object: 'Turma' },
            { subject: 'Professor', predicate: 'lecionaEm', object: 'Turma' },
            { subject: 'Turma', predicate: 'pertenceA', object: 'Escola' },
            { subject: 'Professor', predicate: 'ministra', object: 'Disciplina' },
            { subject: 'Disciplina', predicate: 'fazParteDe', object: 'Turma' },
            { subject: 'Avaliacao', predicate: 'avalia', object: 'Aluno' },
            { subject: 'Avaliacao', predicate: 'relacionaSeA', object: 'Disciplina' },
            { subject: 'Nota', predicate: 'atribuidaA', object: 'Aluno' },
            { subject: 'Nota', predicate: 'referenteA', object: 'Avaliacao' }
        ]
    },
    {
        id: 'v4', name: 'v4 - Recursos e Espaços',
        desc: 'Modelagem de recursos físicos, salas e equipamentos da escola.',
        date: '2024-07-22',
        classes: [
            { id: 'Escola', label: 'Escola' },
            { id: 'Aluno', label: 'Aluno' },
            { id: 'Professor', label: 'Professor' },
            { id: 'Turma', label: 'Turma' },
            { id: 'Disciplina', label: 'Disciplina' },
            { id: 'Avaliacao', label: 'Avaliação' },
            { id: 'Nota', label: 'Nota' },
            { id: 'Sala', label: 'Sala' },
            { id: 'Recurso', label: 'Recurso' }
        ],
        relations: [
            { subject: 'Aluno', predicate: 'estudaEm', object: 'Turma' },
            { subject: 'Professor', predicate: 'lecionaEm', object: 'Turma' },
            { subject: 'Turma', predicate: 'pertenceA', object: 'Escola' },
            { subject: 'Professor', predicate: 'ministra', object: 'Disciplina' },
            { subject: 'Disciplina', predicate: 'fazParteDe', object: 'Turma' },
            { subject: 'Avaliacao', predicate: 'avalia', object: 'Aluno' },
            { subject: 'Avaliacao', predicate: 'relacionaSeA', object: 'Disciplina' },
            { subject: 'Nota', predicate: 'atribuidaA', object: 'Aluno' },
            { subject: 'Nota', predicate: 'referenteA', object: 'Avaliacao' },
            { subject: 'Turma', predicate: 'utiliza', object: 'Sala' },
            { subject: 'Sala', predicate: 'contem', object: 'Recurso' }
        ]
    },
    {
        id: 'v5', name: 'v5 - Calendário e Eventos',
        desc: 'Versão mais completa com calendário escolar, eventos e horários.',
        date: '2024-09-05',
        classes: [
            { id: 'Escola', label: 'Escola' },
            { id: 'Aluno', label: 'Aluno' },
            { id: 'Professor', label: 'Professor' },
            { id: 'Turma', label: 'Turma' },
            { id: 'Disciplina', label: 'Disciplina' },
            { id: 'Avaliacao', label: 'Avaliação' },
            { id: 'Nota', label: 'Nota' },
            { id: 'Sala', label: 'Sala' },
            { id: 'Recurso', label: 'Recurso' },
            { id: 'Evento', label: 'Evento' },
            { id: 'Horario', label: 'Horário' }
        ],
        relations: [
            { subject: 'Aluno', predicate: 'estudaEm', object: 'Turma' },
            { subject: 'Professor', predicate: 'lecionaEm', object: 'Turma' },
            { subject: 'Turma', predicate: 'pertenceA', object: 'Escola' },
            { subject: 'Professor', predicate: 'ministra', object: 'Disciplina' },
            { subject: 'Disciplina', predicate: 'fazParteDe', object: 'Turma' },
            { subject: 'Avaliacao', predicate: 'avalia', object: 'Aluno' },
            { subject: 'Avaliacao', predicate: 'relacionaSeA', object: 'Disciplina' },
            { subject: 'Nota', predicate: 'atribuidaA', object: 'Aluno' },
            { subject: 'Nota', predicate: 'referenteA', object: 'Avaliacao' },
            { subject: 'Turma', predicate: 'utiliza', object: 'Sala' },
            { subject: 'Sala', predicate: 'contem', object: 'Recurso' },
            { subject: 'Evento', predicate: 'ocorreEm', object: 'Escola' },
            { subject: 'Evento', predicate: 'envolve', object: 'Turma' },
            { subject: 'Horario', predicate: 'define', object: 'Disciplina' },
            { subject: 'Horario', predicate: 'alocadoEm', object: 'Sala' }
        ]
    }
];

// ============================================================
// ESTADO GLOBAL
// ============================================================
let currentVersionIndex = 0;
let selectedNodeId = null;

// Elementos
const timelineEl = document.getElementById('timeline');
const detailArea = document.getElementById('detailArea');
const navbarVersion = document.getElementById('navbarVersion');
const currentVersionLabel = document.getElementById('currentVersionLabel');
const btnPrev = document.getElementById('btnPrev');
const btnNext = document.getElementById('btnNext');
const graphArea = document.getElementById('graphArea');
const canvas = document.getElementById('ontologyCanvas');

// Three.js globals
let scene, camera, renderer, raycaster, mouse;
let nodeMeshes = [];        // esferas clicáveis
let relationMeshes = [];     // linhas entre nós
let labelSprites = [];       // rótulos das classes
let predicateSprites = [];   // rótulos das relações
let nodePositions3D = {};    // id -> Vector3
let animationId = null;

// Controle de órbita manual (sem OrbitControls, para evitar dependência extra)
let isDragging = false;
let prevMouse = { x: 0, y: 0 };
let spherical = { radius: 220, theta: Math.PI / 4, phi: Math.PI / 3 };
let cameraTarget = new THREE.Vector3(0, 0, 0);

// ============================================================
// UTILITÁRIOS
// ============================================================
function getCurrentVersion() { return ontologyVersions[currentVersionIndex]; }

// ============================================================
// TIMELINE
// ============================================================
function renderTimeline() {
    timelineEl.innerHTML = '';
    ontologyVersions.forEach((version, index) => {
        const item = document.createElement('div');
        item.className = 'timeline-item' + (index === currentVersionIndex ? ' active' : '');
        item.dataset.index = index;

        const dot = document.createElement('div');
        dot.className = 'timeline-dot';

        const content = document.createElement('div');
        content.className = 'timeline-content';

        const versionName = document.createElement('div');
        versionName.className = 'timeline-version';
        versionName.textContent = version.name;

        const desc = document.createElement('div');
        desc.className = 'timeline-desc';
        desc.textContent = version.desc;

        const date = document.createElement('div');
        date.className = 'timeline-date';
        date.textContent = '📅 ' + version.date;

        content.appendChild(versionName);
        content.appendChild(desc);
        content.appendChild(date);

        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = `Clique para visualizar ${version.name}`;

        item.appendChild(dot);
        item.appendChild(content);
        item.appendChild(tooltip);
        item.addEventListener('click', () => selectVersion(index));
        timelineEl.appendChild(item);
    });
}

// ============================================================
// SELEÇÃO DE VERSÃO
// ============================================================
function selectVersion(index) {
    if (index < 0 || index >= ontologyVersions.length) return;
    currentVersionIndex = index;
    selectedNodeId = null;

    document.querySelectorAll('.timeline-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });

    const version = getCurrentVersion();
    navbarVersion.textContent = version.id;
    currentVersionLabel.textContent = version.id;
    btnPrev.disabled = currentVersionIndex === 0;
    btnNext.disabled = currentVersionIndex === ontologyVersions.length - 1;

    showPlaceholder();
    buildGraph3D();
}

// ============================================================
// INICIALIZAÇÃO DO THREE.JS
// ============================================================
function initThree() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1426);
    scene.fog = new THREE.Fog(0x0b1426, 400, 900);

    // Câmera
    camera = new THREE.PerspectiveCamera(
        50,
        graphArea.clientWidth / graphArea.clientHeight,
        0.1,
        2000
    );
    updateCameraPosition();

    // Renderer
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(graphArea.clientWidth, graphArea.clientHeight, false);

    // Luzes
    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
    keyLight.position.set(120, 180, 150);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x6ea8ff, 0.5);
    fillLight.position.set(-150, -100, -100);
    scene.add(fillLight);

    const rimLight = new THREE.PointLight(0x27ae60, 0.6, 500);
    rimLight.position.set(0, 200, -200);
    scene.add(rimLight);

    // Céu estrelado (partículas)
    addStarfield();

    // Raycaster
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    // Eventos
    setupPointerEvents();

    // Loop
    animate();
}

function addStarfield() {
    const geometry = new THREE.BufferGeometry();
    const count = 600;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 1200;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 1200;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 1200;
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
        color: 0x6ea8ff, size: 1.4, transparent: true, opacity: 0.55
    });
    scene.add(new THREE.Points(geometry, material));
}

// ============================================================
// CONSTRUÇÃO DO GRAFO 3D
// ============================================================
function buildGraph3D() {
    // Remove elementos antigos
    [...nodeMeshes, ...relationMeshes, ...labelSprites, ...predicateSprites].forEach(obj => {
        if (obj.parent) obj.parent.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
            if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
            else obj.material.dispose();
        }
    });
    nodeMeshes = [];
    relationMeshes = [];
    labelSprites = [];
    predicateSprites = [];
    nodePositions3D = {};

    const version = getCurrentVersion();
    const N = version.classes.length;
    const radius = N <= 4 ? 70 : N <= 7 ? 95 : 115;

    // Distribui os nós em uma esfera (distribuição Fibonacci)
    version.classes.forEach((cls, i) => {
        const y = 1 - (i / Math.max(1, N - 1)) * 2;   // 1 .. -1
        const radiusAtY = Math.sqrt(1 - y * y);
        const theta = i * Math.PI * (3 - Math.sqrt(5)); // ângulo áureo

        const x = Math.cos(theta) * radiusAtY;
        const z = Math.sin(theta) * radiusAtY;

        const pos = new THREE.Vector3(
            x * radius,
            y * radius * 0.85,
            z * radius
        );
        nodePositions3D[cls.id] = pos;

        // Esfera
        const geo = new THREE.SphereGeometry(18, 32, 32);
        const mat = new THREE.MeshPhongMaterial({
            color: 0x2a5298,
            emissive: 0x0e2a5c,
            shininess: 90,
            specular: 0x9fc3ff
        });
        const sphere = new THREE.Mesh(geo, mat);
        sphere.position.copy(pos);
        sphere.userData = { id: cls.id, label: cls.label };
        scene.add(sphere);
        nodeMeshes.push(sphere);

        // Halo luminoso
        const haloGeo = new THREE.SphereGeometry(22, 24, 24);
        const haloMat = new THREE.MeshBasicMaterial({
            color: 0x6ea8ff, transparent: true, opacity: 0.12
        });
        const halo = new THREE.Mesh(haloGeo, haloMat);
        halo.position.copy(pos);
        scene.add(halo);
        sphere.userData.halo = halo;

        // Rótulo (sprite)
        const labelSprite = makeTextSprite(cls.label, {
            fontsize: 34, fontface: 'Segoe UI',
            color: '#ffffff',
            bg: 'rgba(20,40,80,0.85)',
            border: 'rgba(110,168,255,0.6)'
        });
        labelSprite.position.set(pos.x, pos.y + 30, pos.z);
        labelSprite.scale.set(60, 18, 1);
        scene.add(labelSprite);
        labelSprites.push(labelSprite);
        sphere.userData.labelSprite = labelSprite;
    });

    // Arestas (tubos com setas)
    version.relations.forEach(rel => {
        const p1 = nodePositions3D[rel.subject];
        const p2 = nodePositions3D[rel.object];
        if (!p1 || !p2) return;

        const dir = new THREE.Vector3().subVectors(p2, p1).normalize();
        const start = p1.clone().add(dir.clone().multiplyScalar(20));
        const end = p2.clone().add(dir.clone().multiplyScalar(-20));
        const length = start.distanceTo(end);
        const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);

        // Tubo
        const tubeGeo = new THREE.CylinderGeometry(1.4, 1.4, length, 8);
        const tubeMat = new THREE.MeshPhongMaterial({
            color: 0x3f6fb5, emissive: 0x0a1e3c, shininess: 60
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);

        // Orienta o cilindro na direção da aresta
        tube.position.copy(mid);
        tube.quaternion.setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            dir
        );
        scene.add(tube);
        tube.userData = { subject: rel.subject, object: rel.object, predicate: rel.predicate };
        relationMeshes.push(tube);

        // Cone da seta
        const coneGeo = new THREE.ConeGeometry(4, 11, 12);
        const coneMat = new THREE.MeshPhongMaterial({
            color: 0x6ea8ff, emissive: 0x1a3a6e
        });
        const cone = new THREE.Mesh(coneGeo, coneMat);
        cone.position.copy(end);
        cone.quaternion.setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            dir
        );
        scene.add(cone);
        relationMeshes.push(cone);
        tube.userData.cone = cone;

        // Rótulo do predicado no meio
        const predSprite = makeTextSprite(rel.predicate, {
            fontsize: 26, fontface: 'Segoe UI',
            color: '#c8d9f0',
            bg: 'rgba(11,20,38,0.75)',
            border: 'rgba(63,111,181,0.5)'
        });
        predSprite.position.copy(mid);
        predSprite.scale.set(50, 14, 1);
        scene.add(predSprite);
        predicateSprites.push(predSprite);
        tube.userData.predSprite = predSprite;
    });

    // Ajusta câmera para enquadrar
    fitCameraToGraph();
}

// Sprite de texto usando canvas 2D
function makeTextSprite(text, opts = {}) {
    const fontsize = opts.fontsize || 32;
    const fontface = opts.fontface || 'Arial';
    const color = opts.color || '#ffffff';
    const bg = opts.bg || 'rgba(0,0,0,0.6)';
    const border = opts.border || 'rgba(255,255,255,0.3)';

    const canvas2d = document.createElement('canvas');
    const ctx2d = canvas2d.getContext('2d');
    const padding = 16;
    const font = `600 ${fontsize}px ${fontface}`;
    ctx2d.font = font;
    const textWidth = ctx2d.measureText(text).width;

    canvas2d.width = Math.ceil(textWidth + padding * 2);
    canvas2d.height = Math.ceil(fontsize + padding * 1.4);

    // Fundo arredondado
    ctx2d.font = font;
    const w = canvas2d.width, h = canvas2d.height, r = 10;
    ctx2d.beginPath();
    ctx2d.moveTo(r, 0);
    ctx2d.arcTo(w, 0, w, h, r);
    ctx2d.arcTo(w, h, 0, h, r);
    ctx2d.arcTo(0, h, 0, 0, r);
    ctx2d.arcTo(0, 0, w, 0, r);
    ctx2d.closePath();
    ctx2d.fillStyle = bg;
    ctx2d.fill();
    ctx2d.lineWidth = 2;
    ctx2d.strokeStyle = border;
    ctx2d.stroke();

    // Texto
    ctx2d.font = font;
    ctx2d.fillStyle = color;
    ctx2d.textAlign = 'center';
    ctx2d.textBaseline = 'middle';
    ctx2d.fillText(text, w / 2, h / 2 + 1);

    const texture = new THREE.CanvasTexture(canvas2d);
    texture.minFilter = THREE.LinearFilter;
    const material = new THREE.SpriteMaterial({
        map: texture, transparent: true, depthTest: false
    });
    const sprite = new THREE.Sprite(material);
    const aspect = w / h;
    sprite.userData.aspect = aspect;
    return sprite;
}

// ============================================================
// CÂMERA
// ============================================================
function updateCameraPosition() {
    if (!camera) return;
    const { radius, theta, phi } = spherical;
    const x = radius * Math.sin(phi) * Math.cos(theta);
    const y = radius * Math.cos(phi);
    const z = radius * Math.sin(phi) * Math.sin(theta);
    camera.position.set(x, y, z);
    camera.lookAt(cameraTarget);
}

function fitCameraToGraph() {
    const version = getCurrentVersion();
    const N = version.classes.length;
    const radius = N <= 4 ? 70 : N <= 7 ? 95 : 115;
    spherical.radius = radius * 2.6;
    spherical.theta = Math.PI / 4;
    spherical.phi = Math.PI / 2.6;
    cameraTarget.set(0, 0, 0);
    updateCameraPosition();
}

// ============================================================
// EVENTOS DE PONTEIRO (rotação, zoom, clique)
// ============================================================
function setupPointerEvents() {
    const el = renderer.domElement;

    el.addEventListener('mousedown', (e) => {
        isDragging = true;
        prevMouse.x = e.clientX;
        prevMouse.y = e.clientY;
    });

    window.addEventListener('mouseup', () => { isDragging = false; });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) {
            updateHover(e);
            return;
        }
        const dx = e.clientX - prevMouse.x;
        const dy = e.clientY - prevMouse.y;
        prevMouse.x = e.clientX;
        prevMouse.y = e.clientY;

        spherical.theta -= dx * 0.006;
        spherical.phi -= dy * 0.006;
        // Limita phi
        spherical.phi = Math.max(0.15, Math.min(Math.PI - 0.15, spherical.phi));
        updateCameraPosition();
    });

    el.addEventListener('wheel', (e) => {
        e.preventDefault();
        spherical.radius *= (e.deltaY > 0 ? 1.08 : 0.92);
        spherical.radius = Math.max(80, Math.min(600, spherical.radius));
        updateCameraPosition();
    }, { passive: false });

    // Clique (apenas se não foi arrasto)
    let downPos = { x: 0, y: 0 };
    el.addEventListener('mousedown', (e) => { downPos = { x: e.clientX, y: e.clientY }; });
    el.addEventListener('click', (e) => {
        const moved = Math.abs(e.clientX - downPos.x) + Math.abs(e.clientY - downPos.y);
        if (moved > 5) return; // foi arrasto

        const rect = el.getBoundingClientRect();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(nodeMeshes, false);
        if (hits.length > 0) {
            const id = hits[0].object.userData.id;
            handleNodeClick(id);
        } else if (selectedNodeId) {
            selectedNodeId = null;
            showPlaceholder();
            updateSelectionVisuals();
        }
    });

    window.addEventListener('resize', onResize);
}

function updateHover(e) {
    if (!raycaster || nodeMeshes.length === 0) return;
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(nodeMeshes, false);
    renderer.domElement.style.cursor = hits.length > 0 ? 'pointer' : 'grab';
}

function onResize() {
    if (!renderer) return;
    const w = graphArea.clientWidth;
    const h = graphArea.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
}

// ============================================================
// SELEÇÃO DE NÓ
// ============================================================
function handleNodeClick(id) {
    selectedNodeId = id;
    const version = getCurrentVersion();
    const cls = version.classes.find(c => c.id === id);
    if (cls) showNodeDetails(cls);
    updateSelectionVisuals();
}

function updateSelectionVisuals() {
    const version = getCurrentVersion();

    // Esferas
    nodeMeshes.forEach(mesh => {
        const isSel = mesh.userData.id === selectedNodeId;
        const connected = isNodeConnected(mesh.userData.id, selectedNodeId);
        const mat = mesh.material;

        if (isSel) {
            mat.color.setHex(0xe67e22);
            mat.emissive.setHex(0x7a3a00);
        } else if (connected) {
            mat.color.setHex(0x27ae60);
            mat.emissive.setHex(0x0d3d20);
        } else {
            mat.color.setHex(0x2a5298);
            mat.emissive.setHex(0x0e2a5c);
        }

        // Halo
        if (mesh.userData.halo) {
            mesh.userData.halo.material.opacity = isSel ? 0.35 : 0.12;
            mesh.userData.halo.material.color.setHex(
                isSel ? 0xffb060 : 0x6ea8ff
            );
        }
    });

    // Arestas
    relationMeshes.forEach(obj => {
        const ud = obj.userData;
        if (!ud || (!ud.subject && !ud.object)) return;
        const active = selectedNodeId &&
            (ud.subject === selectedNodeId || ud.object === selectedNodeId);
        if (obj.geometry.type === 'CylinderGeometry') {
            obj.material.color.setHex(active ? 0x27ae60 : 0x3f6fb5);
            obj.material.emissive.setHex(active ? 0x0d3d20 : 0x0a1e3c);
        } else if (obj.geometry.type === 'ConeGeometry') {
            obj.material.color.setHex(active ? 0x2ecc71 : 0x6ea8ff);
        }
    });

    // Rótulos de predicado — realça os ativos
    version.relations.forEach((rel, idx) => {
        // encontra sprite correspondente por posição (na ordem)
    });
    predicateSprites.forEach((sprite, i) => {
        // heurística: percorre relationMeshes agrupados
    });

    // Melhor: percorre relationMeshes (tubos) e ajusta predSprite
    relationMeshes.forEach(obj => {
        if (obj.userData && obj.userData.predSprite) {
            const ud = obj.userData;
            const active = selectedNodeId &&
                (ud.subject === selectedNodeId || ud.object === selectedNodeId);
            obj.userData.predSprite.material.opacity = active ? 1 : 0.7;
        }
    });
}

function isNodeConnected(id, selId) {
    if (!selId || id === selId) return false;
    const version = getCurrentVersion();
    return version.relations.some(r =>
        (r.subject === selId && r.object === id) ||
        (r.object === selId && r.subject === id)
    );
}

// ============================================================
// DETALHES
// ============================================================
function showPlaceholder() {
    detailArea.innerHTML = `
                <div class="placeholder">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 16v-4M12 8h.01"/>
                    </svg>
                    <p>Clique em uma esfera no grafo 3D para ver seus detalhes e relações.</p>
                </div>
            `;
}

function showNodeDetails(cls) {
    const version = getCurrentVersion();
    const outgoing = version.relations.filter(r => r.subject === cls.id);
    const incoming = version.relations.filter(r => r.object === cls.id);

    let html = `<div class="detail-card">
                <h3>${cls.label}</h3>
                <span class="detail-version-tag">${version.id}</span>
                <p class="detail-desc">Classe da ontologia escolar presente nesta versão.</p>
            `;

    if (outgoing.length > 0) {
        html += `<div class="detail-section-title">Relações de saída</div>
                <ul class="relation-list">`;
        outgoing.forEach(r => {
            html += `<li>
                        <span class="rel-subject">${r.subject}</span>
                        <span class="rel-predicate">${r.predicate}</span>
                        <span class="rel-object">${r.object}</span>
                    </li>`;
        });
        html += `</ul>`;
    }

    if (incoming.length > 0) {
        html += `<div class="detail-section-title">Relações de entrada</div>
                <ul class="relation-list">`;
        incoming.forEach(r => {
            html += `<li>
                        <span class="rel-subject">${r.subject}</span>
                        <span class="rel-predicate">${r.predicate}</span>
                        <span class="rel-object">${r.object}</span>
                    </li>`;
        });
        html += `</ul>`;
    }

    html += `<div class="detail-section-title">Classes nesta versão</div>
            <div class="class-list">`;
    version.classes.forEach(c => {
        const isActive = c.id === cls.id;
        html += `<span class="class-tag" style="${isActive ? 'background:#2a5298;color:#fff;border-color:#2a5298;' : ''}">${c.label}</span>`;
    });
    html += `</div></div>`;

    detailArea.innerHTML = html;
}

// ============================================================
// NAVEGAÇÃO
// ============================================================
btnPrev.addEventListener('click', () => {
    if (currentVersionIndex > 0) selectVersion(currentVersionIndex - 1);
});
btnNext.addEventListener('click', () => {
    if (currentVersionIndex < ontologyVersions.length - 1) selectVersion(currentVersionIndex + 1);
});

// ============================================================
// LOOP DE ANIMAÇÃO
// ============================================================
function animate() {
    animationId = requestAnimationFrame(animate);

    // Rotação suave automática dos rótulos (billboard já é automático)
    // Pulso leve nas esferas selecionadas
    const t = performance.now() * 0.003;
    nodeMeshes.forEach(mesh => {
        if (mesh.userData.id === selectedNodeId) {
            const s = 1 + Math.sin(t) * 0.06;
            mesh.scale.setScalar(s);
            if (mesh.userData.halo) {
                mesh.userData.halo.scale.setScalar(s * 1.05);
            }
        } else {
            mesh.scale.setScalar(1);
            if (mesh.userData.halo) mesh.userData.halo.scale.setScalar(1);
        }
    });

    renderer.render(scene, camera);
}

// ============================================================
// INICIALIZAÇÃO
// ============================================================
function init() {
    renderTimeline();
    initThree();
    selectVersion(0);
}

window.addEventListener('load', () => {
    // pequeno delay para garantir que o layout está calculado
    setTimeout(init, 30);
});
if (document.readyState === 'complete') {
    setTimeout(init, 30);
}