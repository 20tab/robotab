var ws;

var hud = document.getElementById("hud");

var ARENA_WIDTH = 800;
var ARENA_HEIGHT = 600;

var hud_pos = 0;

var scene, camera, eagleCamera, backCamera, renderer, backgroundScene, backgroundCamera;
var superlight;
var keyboard;
var can_use_keyboard = false;

var container;
var raycaster;
var me, avatar;
var players = {};
var walls = [];
var invisible_walls = [];

var objects = [
    {texture: 'ROBO_01_TEXTURE.jpg', object: 'ROBO_01_OK.obj', ref: null},
    {texture: 'ROBO_02_TEXTURE.jpg', object: 'ROBO_02_OK.obj', ref: null},
    {texture: 'muro_texture.jpg'   , object: 'muro.obj'      , ref: null},
];

var avatars = document.getElementsByClassName('choose_player');
for (i in avatars) {
    avatars[i].onclick = function(){
        var username_input = document.getElementById('username_input');
        me = username_input.value;
        var pattern = /^[a-zA-Z0-9- ]*$/;
        if (me == '' || !pattern.test(me)){
            username_input.setAttribute('style', 'border: 5px red solid');
            // username_input.border = "5px red solid;";
        }
        else{
            avatar = this.getAttribute('data-avatar');
            document.getElementById("select_player").remove();
            init();
        }
    }
}

function ws_recv(e) {
    // console.log(e.data);
    var items = e.data.split(':');
    if (items[0] == 'arena') {
        hud.innerHTML = '#' + items[1];
        return;
    }
    if (items[0] == '!') {
        var player = players[items[1]];
        if (player == undefined) {
            return;
        }

        var cmd = items[2];
        var args = cmd.split(',');
        player.bullet.ws['r'] = args[0];
        player.bullet.ws['x'] = args[1];
        player.bullet.ws['y'] = args[2];
        player.bullet.ws['z'] = args[3];
        player.bullet.ws['R'] = args[4];
        player.bullet.dirty = true;
        return;
    }
    if(items[0] == 'walls'){
        var wall_list = items[1].split(';');
        for (var i = 0; i < wall_list.length; i++){
            var args = wall_list[i].split(',');
            add_wall(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        }
        return;
    }

    var player = players[items[0]];
    var cmd = items[1];
    var args = cmd.split(',');
    if (player == undefined) {
        // (name, avatar, x, y, z, r, scale)
        add_player(items[0], args[6], args[1], args[2], args[3], args[0], args[7]);
        player = players[items[0]];
    }
    player.ws['r'] = args[0];
    player.ws['x'] = args[1];
    player.ws['y'] = args[2];
    player.ws['z'] = args[3];
    player.ws['a'] = args[4];
    player.energy = parseFloat(args[5]).toFixed(1);
    if (player.energy > 0){
        player.name_and_energy = items[0] + ': ' + player.energy;
    }
    else{
        player.name_and_energy = items[0] + ' Dead'
    }
    player.dirty = true;
};


function init(){
    // console.log('init');
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);

    camera.position.x = 0;
    camera.position.y = 800;
    camera.position.z = 0;

    eagleCamera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);

    eagleCamera.lookAt(scene.position);
    eagleCamera.position.x = 0;
    eagleCamera.position.y = 5000;
    eagleCamera.position.z = 0;
    eagleCamera.rotation.x = -Math.PI/2;

    scene.add(camera);
    scene.add(eagleCamera);

    backCamera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);

    renderer = new THREE.WebGLRenderer({antialias: true});
    renderer.setSize(ARENA_WIDTH, ARENA_HEIGHT);

    renderer.shadowMapEnabled = true;
    renderer.shadowCameraNear = 3;
    renderer.shadowCameraFar = camera.far;
    renderer.shadowCameraFov = 50;

    renderer.shadowMapBias = 0.0039;
    renderer.shadowMapDarkness = 0.5;
    renderer.shadowMapWidth = 1024;
    renderer.shadowMapHeight = 1024;

    container = document.getElementById("ThreeJS");
    container.appendChild(renderer.domElement);

    var ambient = new THREE.AmbientLight(0x333333);
    scene.add(ambient);

    var floorTexture = new THREE.ImageUtils.loadTexture( 'panel35.jpg' );
    floorTexture.wrapS = floorTexture.wrapT = THREE.RepeatWrapping;
    floorTexture.repeat.set( 10, 10 );
    var floorMaterial = new THREE.MeshPhongMaterial( { map: floorTexture , side: THREE.DoubleSide } );
    var floorGeometry = new THREE.PlaneGeometry(4000, 4000);
    var floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.position.y = -0.5;
    floor.rotation.x = Math.PI / 2;
    floor.receiveShadow = true;

    scene.add(floor);

    var light = new THREE.SpotLight( 0xffffff, 1 );
    light.position.set(-100, 150, 0);
    light.rotation.x += 1.9;

    scene.add(light);

    superlight = light;
    light.castShadow = true;

    var light = new THREE.DirectionalLight(0xffffff, 0.7);
    light.position.set(0, 10, 0);
    scene.add(light);

    var Ltexture = THREE.ImageUtils.loadTexture('skydome.jpg');
    var backgroundMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2, 0),
        new THREE.MeshBasicMaterial({map: Ltexture})
    );

    backgroundMesh.material.depthTest = false;
    backgroundMesh.material.depthWrite = false;

    backgroundScene = new THREE.Scene();
    backgroundCamera = new THREE.Camera();
    backgroundScene.add(backgroundCamera);
    backgroundScene.add(backgroundMesh);
    keyboard = new THREEx.KeyboardState();

    var manager = new THREE.LoadingManager();
    manager.onProgress = function ( item, loaded, total ) {
        // console.log( item, loaded, total );
    };

    loadObjects3d(objects, 0, manager);
}

function start_the_world() {
    ws.send(me + ':' + avatar);
    animate();
}

var clock = new THREE.Clock();

function animate()
{
    setTimeout( function() {
    requestAnimationFrame( animate );
    }, 1000 / 30 );
    render();
    update();
}

var use_eagle_camera = true;
var is_pressing = false;
var camera_changed = false;

function render() {
    // console.log('render');

    renderer.autoClear = false;
    renderer.clear();
    renderer.render(backgroundScene, backgroundCamera);

    if (use_eagle_camera) {
        renderer.render(scene, eagleCamera);
    }
    else {
        renderer.render(scene, backCamera);
    }
}

function update() {
    // console.log('update');
    var rotating = false;
    if (can_use_keyboard){
        if (!is_pressing && keyboard.pressed("c")){

            if (!use_eagle_camera){
                for (var i = 0; i < invisible_walls.length; i++){
                    invisible_walls[i].object.material.opacity = 1;
                }
                invisible_walls = [];
            }
            else {
                camera_changed = true;
            }
            use_eagle_camera = !use_eagle_camera;
            is_pressing = true;
        }
        else if (is_pressing && !keyboard.pressed("c")) {
            is_pressing = false;
        }

        if (keyboard.pressed("space")){
            ws.send(me+":AT");
        }
        // else if (players[me] && players[me].ws['a']){
        //     ws.send(me+":at");
        // }
        if (keyboard.pressed("right")){
            ws.send(me + ":rr");
            rotating = true;
            console.log('rr');
        }
        else if (keyboard.pressed("left")){
            ws.send(me + ":rl");
            rotating = true;
            console.log('rl');
        }
        if (!rotating && keyboard.pressed("up")){
            ws.send(me + ":fw");
        }
        if (!rotating && keyboard.pressed("down")){
            ws.send(me + ":bw");
        }
    }

    Object.keys(players).forEach(function(key){
        var player = players[key];
        if (player.bullet.dirty == true) {
            player.bullet.children[0].visible = true;
            player.bullet.visible = true;
            player.bullet.rotation.y = player.bullet.ws['r'];
            player.bullet.position.x = player.bullet.ws['x'];
            player.bullet.position.y = player.bullet.ws['y'];
            player.bullet.position.z = player.bullet.ws['z'];
            if (player.bullet.ws['R'] <= 0) {
                player.bullet.visible = false;
                player.bullet.children[0].visible = false;
            }
        }

        if (player.dirty) {
            if (player.energy <= 0) {
                remove_player(player);
            }

            draw_hud_div(player);
            player.rotation.y = parseFloat(player.ws['r']);
            player.position.x = parseFloat(player.ws['x']);
            player.position.y = parseFloat(player.ws['y']);
            player.position.z = parseFloat(player.ws['z']);
        }

        if ((player.dirty && player.name == me && !use_eagle_camera) || camera_changed){
            player.updateMatrixWorld();
            var position_vector = new THREE.Vector3();
            var position = position_vector.setFromMatrixPosition(backCamera.matrixWorld);

            var direction = player.position.clone().sub(position).normalize();

            raycaster.set(position, direction);

            var obstacles = raycaster.intersectObjects(walls, true);

            var i;
            for (i = 0; i < invisible_walls.length; i++){
                var j = obstacles.indexOf(invisible_walls[i]);
                if (j >= 0){
                    obstacles.splice(j, 1);
                }
                else {
                    invisible_walls[i].object.material.opacity = 1;
                    invisible_walls.splice(i, 1);
                }
            }
            for (i = 0; i < obstacles.length; i++){
                obstacles[i].object.material.opacity = 0.5;
                invisible_walls.push(obstacles[i]);
            }
            camera_changed = false;
        }
        player.dirty = false;
    });

    if (players[me]){
        camera.lookAt(players[me].position);
    }

    superlight.rotation.x += 0.1;
}

function add_player(name, avatar, x, y, z, r, scale) {
    // console.log('add_player');
    if (avatar == '1'){
        players[name] = objects[0].ref.clone();
    }
    else{
        players[name] = objects[1].ref.clone();
    }
    players[name].children[0].material = players[name].children[0].material.clone()
    players[name].children[0].material.color.setHex(Math.random() * 0xffffff);
    players[name].name = name;
    players[name].scale.set(scale, scale, scale);
    players[name].energy = 100.0;
    players[name].name_and_energy = name + ': 100.0';

    var sphereGeom = new THREE.SphereGeometry(20, 20, 20);
    var blueMaterial = new THREE.MeshBasicMaterial({color: 0xff00ff});
    var bullet = new THREE.Mesh(sphereGeom, blueMaterial);
    bullet.visible = false;
    scene.add(bullet);
    bullet.ws = {};
    players[name].bullet = bullet;

    var spotLight = new THREE.PointLight(0xff00ff, 1.0, 200);
    spotLight.visible = false;
    players[name].bullet.add(spotLight);

    players[name].ws = {'x':0.0, 'y':0.0, 'z':0.0, 'r':0.0, 'a':0};

    var player_hud = document.createElement('div');
    player_hud.id = 'player_' + name;
    player_hud.setAttribute('style', "position:absolute;left:800px;top:" + hud_pos + "px");
    hud_pos += 20;

    document.getElementsByTagName('body')[0].appendChild(player_hud);
    players[name].hud = player_hud;

    draw_hud_div(players[name]);

    if (name == me){
        can_use_keyboard = true;
        players[name].add(backCamera);
        backCamera.position.set(0, 10, -80);
        backCamera.lookAt(players[name].position);
        players[name].updateMatrixWorld();
        var position_vector = new THREE.Vector3();
        var position = position_vector.setFromMatrixPosition(backCamera.matrixWorld);

        var direction = players[name].position.clone().sub(position).normalize();

        raycaster = new THREE.Raycaster(position, direction, 0, 350);
    }
    players[name].position.x = parseFloat(x);
    players[name].position.y = parseFloat(y);
    players[name].position.z = parseFloat(z);
    players[name].rotation.y = parseFloat(r);
    scene.add(players[name]);
}


function remove_player(player){
    scene.remove(player.bullet);
    scene.remove(player);
    // removeReferences(player);
    player.dirty = false;
    delete players[player.name];
    console.log(players);
    if (player.name == me) {
        use_eagle_camera = true;
        can_use_keyboard = false;
    }
}

function add_wall(sc_x, sc_y, sc_z, x, y, z, r) {
    var muro = objects[2].ref.clone();
    muro.children[0].material = muro.children[0].material.clone();
    muro.scale.set(sc_x, sc_y, sc_z)
    muro.position.set(x, y, z);
    muro.rotation.y = r;
    scene.add(muro);
    walls.push(muro);
}

function draw_huds() {
    // console.log('draw_huds');
    Object.keys(players).forEach( function(key) {
        draw_hud_div(players[key]);
    });
}

function draw_hud_div(player) {
    // console.log('draw_hud_div');
    player.hud.innerHTML = player.name_and_energy;
}

function go_fullscreen() {
    // console.log('go_fullscreen');

    if (!THREEx.FullScreen.activated()) {
        THREEx.FullScreen.request(document.getElementById('ThreeJS'));
    }
}

function loadObjects3d(objects3d, index, manager){
    if (index >= objects3d.length){
        objects[2].ref.children[0].material.transparent = true;
        start_websocket();
        return;
    }

    var texture = new THREE.Texture();
    var image_loader = new THREE.ImageLoader(manager);
    image_loader.load(objects3d[index].texture, function (image) {
        texture.image = image;
        texture.needsUpdate = true;
    });

    var obj_loader = new THREE.OBJLoader(manager);
    obj_loader.load(objects3d[index].object, function (object){
        object.traverse(function (child) {
            if (child instanceof THREE.Mesh) {
                child.material.map = texture;
            }
        });
        object.children[0].geometry.computeFaceNormals();
        var  geometry = object.children[0].geometry;
        THREE.GeometryUtils.center(geometry);

        objects3d[index].ref = object;
        loadObjects3d(objects3d, ++index, manager);
    });
}

function start_websocket(){
    ws = new WebSocket('ws://127.0.0.1:8080/robotab');
    ws.onopen = start_the_world;
    ws.onmessage = ws_recv;
    ws.oncolose = function() {
        alert('connection closed');
    }
    ws.onerror = function() {
        alert('ERROR');
    }
}
