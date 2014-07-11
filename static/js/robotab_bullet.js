var ws;

var hud = document.getElementById("hud");

var ARENA_WIDTH = window.innerWidth;
var ARENA_HEIGHT = window.innerHeight;

var hud_pos = 20;

var scene, camera, eagleCamera, backCamera, renderer, backgroundScene, backgroundCamera;
var keyboard;
var can_use_keyboard = false;

var container;
var raycaster;
var me, avatar;
var players = {};
var walls = [];
var invisible_walls = [];
var posters = [];
var bonus_malus = {};
var moving_sphere;
var healtbar;
var health;
var particles, particleSystem;
var particleCount = 500;

var playerParticleSystem, playerPart;

var shootingEngines = [];

var objects = [
    {texture: 'static/img/ROBO_01_TEXTURE.jpg', object: 'static/obj/ROBO_01_OK.obj', ref: undefined},
    {texture: 'static/img/ROBO_02_TEXTURE.jpg', object: 'static/obj/ROBO_02_OK.obj', ref: undefined},
    {texture: 'static/img/missile_texture.jpg', object: 'static/obj/missile.obj'   , ref: undefined},
    {texture: 'static/img/muro_texture.jpg'   , object: 'static/obj/muro.obj'      , ref: undefined},
    {texture: undefined                       , object: 'static/obj/power.obj'     , ref: undefined, color:0xFF0000},
    {texture: undefined                       , object: 'static/obj/heal.obj'      , ref: undefined, color:0x00FF00},
    {texture: undefined                       , object: 'static/obj/haste.obj'     , ref: undefined, color:0x0000FF},
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
            document.getElementById('ready' + avatar).play();
            document.getElementById("select_player").remove();
            init();
        }
    }
}

function ws_recv(e) {
    //console.log(e.data);
    var items = e.data.split(':');
    if (items[0] == 'arena') {
        var args = items[1].split(',');
        if (args[0] == 'bm'){
            if(args[1] == 'gv'){
                if(args[3] != 'heal'){
                    players[args[4]].bonus += " " + args[3];
                }
                remove_bonus_malus(args[2]);
            }
            else if(args[1] == 'rm'){
                players[args[3]].bonus = players[args[3]].bonus.replace(" " + args[2], "");
            }
            else{
                add_bonus_malus(args[1], args[2], args[3], args[4], args[5]);
            }
        }
        else{
            hud.innerHTML = '#' + items[1];
        }
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
        player.bullet.ws['R'] = parseFloat(args[4]);
        player.bullet.dirty = true;
        return;
    }

    if (items[0] == 'kill'){

        var args = items[1].split(',');
        if (args[0] == 'winner'){
            players[args[1]].name_and_energy = players[args[1]].name + ': Winner';
            draw_hud_div(players[args[1]]);
            var huds = document.getElementsByClassName('players_energy');
            while(huds.length > 0){
                huds[0].parentNode.removeChild(huds[0]);
            }
            hud_pos = 20;
        }
        else if (args[0] == 'loser'){
            players[args[1]].name_and_energy = players[args[1]].name + ': Dead';
        }
        else if (args[0] == 'leaver'){
            players[args[1]].name_and_energy = players[args[1]].name + ': Leaver';

        }
        draw_hud_div(players[args[1]]);
        if (args[1] == me){
            can_use_keyboard = false;
            use_eagle_camera = true;
            document.getElementById('arrows').remove();
            document.getElementById('healthbar').remove();
            var h2_class, text;
            if (args[0] == 'winner'){
                h2_class = 'winner';
                text = 'VICTORY';
            }
            else{
                h2_class = 'loser';
                text = 'GAME OVER';
            }
            game_over(h2_class, text);
        }
        remove_player(players[args[1]]);
        return;
    }

    if (items[0] == 'ground'){
        var args = items[1].split(',');
        add_ground(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        return; 
    }
    if (items[0] == 'wall'){
        var args = items[1].split(',');
        add_wall(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        return;
    }
    
    if (items[0] == 'ramp'){
        var args = items[1].split(',');
        add_ramp(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        return;
    }

    if (items[0] == 'posters') {
        posters = items[1].split(';');
        return;
    }
    if (items[0] == 'sphere'){
        var args = items[1].split(',');
        console.log(items[1]);
        if (moving_sphere == undefined){
            add_sphere(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        }
        else{
            moving_sphere.ws['x'] = args[1];
            moving_sphere.ws['y'] = args[2];
            moving_sphere.ws['z'] = args[3];
            moving_sphere.ws['rot_x'] = parseFloat(args[4]);
            moving_sphere.ws['rot_y'] = parseFloat(args[5]);
            moving_sphere.ws['rot_z'] = parseFloat(args[6]);
            moving_sphere.ws['rot_w'] = parseFloat(args[7]);
            moving_sphere.dirty = true;
        }
        return;
    }

    var player = players[items[0]];
    var cmd = items[1];
    var args = cmd.split(',');
    if (player == undefined) {
        add_player(
            items[0],               //name
            parseFloat(args[0]),    //x
            parseFloat(args[1]),    //y
            parseFloat(args[2]),    //z
            parseFloat(args[3]),    //rot_x
            parseFloat(args[4]),    //rot_y
            parseFloat(args[5]),    //rot_z
            parseFloat(args[6]),    //rot_w
            parseFloat(args[7]),    //energy
            parseInt(args[8]),      //avatar
            parseFloat(args[9]),    //sc_x
            parseFloat(args[10]),   //sc_y
            parseFloat(args[11]),   //sc_z
            parseInt(args[12]));    //color
            // player = players[items[0]];
        return;
    }

    player.ws['x'] = parseFloat(args[0]);
    player.ws['y'] = parseFloat(args[1]);
    player.ws['z'] = parseFloat(args[2]);
    player.ws['rot_x'] = parseFloat(args[3]);
    player.ws['rot_y'] = parseFloat(args[4]);
    player.ws['rot_z'] = parseFloat(args[5]);
    player.ws['rot_w'] = parseFloat(args[6]);
    player.ws['velocity'] = parseFloat(args[13]);

    player.energy = parseFloat(args[7]);
    player.name_and_energy = items[0] + ': ' + player.energy;
    player.dirty = true;
};


function init(){
    // console.log('init');
    scene = new THREE.Scene();

    eagleCamera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);
    eagleCamera.lookAt(scene.position);
    eagleCamera.position.x = 0;
    eagleCamera.position.y = 5000;
    eagleCamera.position.z = 0;
    eagleCamera.rotation.x = -Math.PI/2;
    scene.add(eagleCamera);

    backCamera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);

    renderer = new THREE.WebGLRenderer({antialias: true});
    renderer.setSize(ARENA_WIDTH, ARENA_HEIGHT);
    //renderer.shadowMapEnabled = true;

    container = document.getElementById("ThreeJS");
    container.appendChild(renderer.domElement);

    //var ambient = new THREE.AmbientLight(0x333333);
    //scene.add(ambient);

    var spotlight = new THREE.PointLight(0xffffff, 1, 0);
    spotlight.position.set(-2000, 2000, 2000);
    scene.add(spotlight);
    var spotlight = new THREE.PointLight(0xffffff, 1, 0);
    spotlight.position.set(2000, 2000, 2000);
    scene.add(spotlight);
    var spotlight = new THREE.PointLight(0xffffff, 1, 0);
    spotlight.position.set(2000, 2000, -7000);
    scene.add(spotlight);
    var spotlight = new THREE.PointLight(0xffffff, 1, 0);
    spotlight.position.set(-2000, 2000, -7000);
    scene.add(spotlight);
    //var floorTexture = new THREE.ImageUtils.loadTexture( 'static/img/panel35.jpg' );
    //floorTexture.wrapS = floorTexture.wrapT = THREE.RepeatWrapping;
    //floorTexture.repeat.set( 10, 10 );
    //var floorMaterial = new THREE.MeshPhongMaterial( { map: floorTexture , side: THREE.DoubleSide } );
    //var floorGeometry = new THREE.PlaneGeometry(4000, 4000);
    //var floor = new THREE.Mesh(floorGeometry, floorMaterial);
    //floor.position.y = -0.5;
    //floor.rotation.x = Math.PI / 2;
    ////floor.receiveShadow = true;
    //scene.add(floor);


    //var spotlight = new THREE.SpotLight(0xffffff);
    //spotlight.position.set(-2000, 450, -2000);
    ////spotlight.shadowCameraVisible = true;
    ////spotlight.shadowDarkness = 0.95;
    //spotlight.intensity = 2;
    //// must enable shadow casting ability for the light
    ////spotlight.castShadow = true;
    //scene.add(spotlight);

    //var spotlight = new THREE.SpotLight(0xffffff);
    //    spotlight.position.set(2000, 450, 2000);
    //    //spotlight.shadowCameraVisible = true;
    //    //spotlight.shadowDarkness = 0.95;
    //    spotlight.intensity = 2;
    //    // must enable shadow casting ability for the light
    //    //spotlight.castShadow = true;
    //    scene.add(spotlight);

    //var spotlight = new THREE.SpotLight(0xffffff);
    //    spotlight.position.set(2000, 450, -2000);
    //    //spotlight.shadowCameraVisible = true;
    //    //spotlight.shadowDarkness = 0.95;
    //    spotlight.intensity = 2;
    //    // must enable shadow casting ability for the light
    //    //spotlight.castShadow = true;
    //    scene.add(spotlight);

    //var spotlight = new THREE.SpotLight(0xffffff);
    //    spotlight.position.set(-2000, 450, 2000);
    //    //spotlight.shadowCameraVisible = true;
    //    //spotlight.shadowDarkness = 0.95;
    //    spotlight.intensity = 2;
    //    // must enable shadow casting ability for the light
    //    //spotlight.castShadow = true;
    //    scene.add(spotlight);


    var Ltexture = THREE.ImageUtils.loadTexture('static/img/nebula.jpg');
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


    particles = new THREE.Geometry();
    var pMaterial = new THREE.ParticleBasicMaterial({
        color: 0xFFFFFF,
        size: 1,
        map: THREE.ImageUtils.loadTexture(
            "static/img/particle.png"
        ),
        blending: THREE.AdditiveBlending,
        transparent: true
    });

    for (var p = 0; p < particleCount; p++) {

        // create a particle with random
        // position values, -2000 -> 2000
        var pX = Math.random() * 4000 - 2000,
            pY = Math.random() * 300,
            pZ = Math.random() * 4000 - 2000,
            particle = new THREE.Vector3(pX, pY, pZ);

        // add it to the geometry
        particles.vertices.push(particle);
        particle.velocity = new THREE.Vector3(
            0,              // x
            -Math.random(), // y: random vel
            0);
    }
    particleSystem = new THREE.ParticleSystem(
    particles,
    pMaterial);

    particleSystem.sortParticles = true;
    particleSystem.visible = false;
    // add it to the scene
    scene.add(particleSystem);

    var manager = new THREE.LoadingManager();
    manager.onProgress = function ( item, loaded, total ) {
        // console.log( item, loaded, total );
    };

    loadObjects3d(objects, 0, manager);
}

var stats;

function start_the_world() {
    ws.send(me + ':' + avatar);
    animate();

    stats = new Stats();
    stats.setMode(0); // 0: fps, 1: ms

    // Align top-left
    stats.domElement.style.position = 'absolute';
    stats.domElement.style.left = '0px';
    stats.domElement.style.bottom = '0px';
    document.getElementById('ThreeJS').appendChild(stats.domElement);
    //document.body.appendChild( stats.domElement );
}

var clock = new THREE.Clock();

function animate() {
    setTimeout( function() {
        stats.begin();

        requestAnimationFrame( animate );
        render();
        update(clock.getDelta());

        stats.end();
    }, 1000.0 / 33.33 );
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
        Object.keys(players).forEach(function(key){
        	var player = players[key];
		player.sound.update(backCamera);
	});
    }
}

function update(td) {
    // console.log('update');
    var rotating = false;
    if (can_use_keyboard){
        if (!is_pressing && keyboard.pressed("c")){

            if (!use_eagle_camera){
                for (var i = 0; i < invisible_walls.length; i++){
                    invisible_walls[i].object.material.opacity = 1;
                }
                invisible_walls = [];
                add_eagle_camera_arrows();
                document.getElementById('zoom-in').onclick = move_eagle_camera_in;
                document.getElementById('zoom-out').onclick = move_eagle_camera_out;
                particleSystem.visible = false;
            }
            else {
                remove_eagle_camera_arrows();
                document.getElementById('zoom-in').onclick = move_back_camera_in;
                document.getElementById('zoom-out').onclick = move_back_camera_out;
                particleSystem.visible = true;
                camera_changed = true;
            }
            use_eagle_camera = !use_eagle_camera;
            is_pressing = true;
        }
        else if (is_pressing && !keyboard.pressed("c")) {
            is_pressing = false;
        }

        if (keyboard.pressed("space")){
            ws.send(me + ":AT");
        }
/*
         else if (players[me] && players[me].ws['a']){
             ws.send(me+":at");
         }
*/

        var is_moving = false;

        if (keyboard.pressed("d")){
            ws.send(me + ":rr");
            rotating = true;
            is_moving = true;
        }
        else if (keyboard.pressed("a")){
            ws.send(me + ":rl");
            rotating = true;
            is_moving = true;
        }


        if (!rotating && keyboard.pressed("w")){
            ws.send(me + ":fw");
            is_moving = true;
        }

        if (!rotating && keyboard.pressed("s")){
            ws.send(me + ":bw");
            is_moving = true;
        }

/*
        if (is_moving) {
            if (document.getElementById('move').paused) {
                document.getElementById('move').play();
            }
        }
        else {
            if (!document.getElementById('move').paused) {
                document.getElementById('move').pause();
                document.getElementById('move').currentTime = 0;
            }
        }
*/
    }
    if (moving_sphere != undefined && moving_sphere.dirty){
        moving_sphere.position.set(
            parseFloat(moving_sphere.ws['x']),
            parseFloat(moving_sphere.ws['y']),
            parseFloat(moving_sphere.ws['z']));
        moving_sphere.quaternion.set(
            moving_sphere.ws['rot_x'],
            moving_sphere.ws['rot_y'],
            moving_sphere.ws['rot_z'],
            moving_sphere.ws['rot_w']);
        moving_sphere.dirty = false;
    }

    Object.keys(bonus_malus).forEach(function(key){
        var bm = bonus_malus[key];
        bm.rotation.y += 0.1;
    });

    Object.keys(players).forEach(function(key){
        var player = players[key];
        if (player.bullet.dirty == true) {
            if (document.getElementById('fire').paused) {
                //document.getElementById('fire').pause();
                document.getElementById('fire').currentTime = 0;
                document.getElementById('fire').play();
            }
            player.bullet.dirty = false;

            if (player.bullet.ws['R'] <= 0) {
                //player.bullet.children[0].visible = false;
                player.bullet.visible = false;
                document.getElementById('fire').pause();
                return;
            }
            else if (player.bullet.ws['R'] >= player.last_bullet){
                player.engineGroup.triggerPoolEmitter( 1, new THREE.Vector3( 0, 3, 10) );
            }
            //player.bullet.children[0].visible = true;
            player.bullet.visible = true;
            player.bullet.rotation.y = player.bullet.ws['r'];
            player.bullet.position.x = player.bullet.ws['x'];
            player.bullet.position.y = player.bullet.ws['y'];
            player.bullet.position.z = player.bullet.ws['z'];
            player.last_bullet = player.bullet.ws['R'];
        }

        if (player.dirty) {
            draw_hud_div(player);
            //player.rotation.setFromQuaternion(
            //    new THREE.Quaternion(
            //        player.ws['rot_x'],
            //        player.ws['rot_y'],
            //        player.ws['rot_z'],
            //        player.ws['rot_w']));
            player.quaternion.set(
                player.ws['rot_x'],
                player.ws['rot_y'],
                player.ws['rot_z'],
                player.ws['rot_w']);
            player.position.set(
                player.ws['x'],
                player.ws['y'],
                player.ws['z']);
            player.sound.source.playbackRate.value = player.ws['velocity'] / 45;
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
            var percentage = player.energy / 100.0;
            health.style.width = ((200 * player.energy) / 100.0) + 'px';
        }
        player.dirty = false;
    });

    if(!use_eagle_camera){
        particleSystem.rotation.y += 0.01;
        var pCount = particleCount;
        while (pCount--) {

            // get the particle
            var particle = particles.vertices[pCount];

            // check if we need to reset
            if (particle.y < 0) {
                particle.y = 200;
                particle.velocity.y = 0;
            }

            // update the velocity with
            // a splat of randomniz
            particle.velocity.y -= Math.random() * .1;

            // and the position
            particle.add(particle.velocity);
        }

        // flag to the particle system
        // that we've changed its vertices.
        particleSystem.geometry.__dirtyVertices = true;
    }

    for(i in shootingEngines){
        shootingEngines[i].tick(td);
    }
}

function add_player(name, x, y, z, rot_x, rot_y, rot_z, rot_w, energy, avatar, sc_x, sc_y, sc_z, color) {
    // console.log('add_player');
    if (avatar == 1){
        players[name] = objects[0].ref.clone();
    }
    else{
        players[name] = objects[1].ref.clone();
    }
    players[name].children[0].material = players[name].children[0].material.clone()
    players[name].children[0].material.color.setHex(color);
    players[name].name = name;
    console.log(sc_x, sc_y, sc_z);
    players[name].scale.set(sc_x, sc_y, sc_z);
    players[name].energy = energy;
    players[name].name_and_energy = name + ': ' + energy;
    players[name].bonus = '';
    players[name].last_bullet = 0;
    players[name].sound = new THREE.AudioObject( [ 'static/sounds/move-loop.mp3' ]);
    players[name].add(players[name].sound);
    // Create a single Emitter

    var playerEngineGroup = new SPE.Group({
        // Give the particles in this group a texture
        texture: THREE.ImageUtils.loadTexture('static/img/particle.png'),
        blending: THREE.AdditiveBlending,
        // How long should the particles live for? Measured in seconds.
        maxAge: 0.1,
    });

    var emitterSettings = {
        type: 'sphere',
        radius: 1,
        speed: 100,

        accelerationSpread: new THREE.Vector3(
            Math.random(),
            Math.random(),
            Math.random()
        ),

        velocitySpread: new THREE.Vector3(
            Math.random(),
            Math.random(),
            Math.random()
        ),
        particlesPerSecond: 100,
        sizeStart: 2,
        sizeEnd: 0,
        opacityStart: 1,
        opacityEnd: 0,
        colorStart: new THREE.Color(color),
        colorEnd: new THREE.Color('white'),
        alive: 0,
        duration: 0.1
    };

    players[name].engineGroup = playerEngineGroup;
    playerEngineGroup.addPool( 10, emitterSettings, true );

    scene.add(playerEngineGroup.mesh);

    shootingEngines.push(playerEngineGroup);
    players[name].add(playerEngineGroup.mesh);

    var geometry = new THREE.SphereGeometry( 3, 32, 32 );
    var material = new THREE.MeshPhongMaterial({ transparent: true, opacity: 0.7});
    material.color.setHex(color);
    var bullet = new THREE.Mesh( geometry, material );

    bullet.scale.set(sc_x, sc_y, sc_z);
    //bullet.children[0].visible = false;
    bullet.visible = false;
    //var axis = new THREE.Vector3(0, 1, 0);
    //bullet.rotateOnAxis(axis, 90);
    scene.add(bullet);
    bullet.ws = {};
    players[name].bullet = bullet;

    players[name].ws = {
        'x': 0.0,
        'y': 0.0,
        'z': 0.0,
        'rot_x': 0.0,
        'rot_y': 0.0,
        'rot_z': 0.0,
        'rot_w': 0.0,
    };

    var player_hud = document.createElement('div');
    player_hud.id = 'player_' + name;
    player_hud.setAttribute('style', "top:" + hud_pos + "px");
    player_hud.className = 'players_energy';
    hud_pos += 20;

    document.getElementById('ThreeJS').appendChild(player_hud);
    players[name].hud = player_hud;

    draw_hud_div(players[name]);

    if (name == me){
        can_use_keyboard = true;
        players[name].add(backCamera);
        backCamera.position.set(0, 20, -80);
        backCamera.lookAt(players[name].position);
        players[name].updateMatrixWorld();
        var position_vector = new THREE.Vector3();
        var position = position_vector.setFromMatrixPosition(backCamera.matrixWorld);

        var direction = players[name].position.clone().sub(position).normalize();

        raycaster = new THREE.Raycaster(position, direction, 0, 350);
        use_eagle_camera = false;
        add_camera_focus();

        create_and_append_elements_to_father([['div', 'healthbar', '', '', '']], 'ThreeJS');
        create_and_append_elements_to_father([['div', 'health', '', '', '']], 'healthbar');

        health = document.getElementById('health');
        particleSystem.visible = true;

    }

    players[name].position.x = x;
    players[name].position.y = y;
    players[name].position.z = z;
    players[name].quaternion.set(rot_x, rot_y, rot_z, rot_w);
    scene.add(players[name]);
}


function remove_player(player){
    scene.remove(player.bullet);
    scene.remove(player);
    // removeReferences(player);
    player.dirty = false;
    delete players[player.name];
}

function add_bonus_malus(id, bm_type, x, y, z){
    if (bm_type == 'power') {
        bonus_malus[id] = objects[4].ref.clone();
    }
    else if (bm_type == 'heal') {
        bonus_malus[id] = objects[5].ref.clone();
    }
    else if (bm_type == 'haste') {
        bonus_malus[id] = objects[6].ref.clone();
    }
    else {
        return;
    }
    bonus_malus[id].children[0].material = bonus_malus[id].children[0].material.clone();
    bonus_malus[id].scale.set(7, 7, 7);
    bonus_malus[id].position.set(x, y, z);
    scene.add(bonus_malus[id]);
}

function remove_bonus_malus(id){
    scene.remove(bonus_malus[id]);
    delete bonus_malus[id];
}

function add_sphere(radius, x, y, z, rot_x, rot_y, rot_z, rot_w){
    var geometry = new THREE.SphereGeometry(40, 16, 16);//parseInt(radius), 16, 16);
    var sphereTexture = new THREE.ImageUtils.loadTexture('static/img/skel.jpg');
    sphereTexture.repeat.set(1, 1);
    sphereTexture.wrapS = sphereTexture.wrapT = THREE.RepeatWrapping;
    var sphereMaterial = new THREE.MeshPhongMaterial({map: sphereTexture});
    moving_sphere = new THREE.Mesh(geometry, sphereMaterial);
    moving_sphere.position.set(x, y, z);
    //moving_sphere.useQuaternion = true;
    moving_sphere.quaternion.set(rot_x, rot_y, rot_z, rot_w);
    moving_sphere.ws = {
        'x': 0.0,
        'y': 0.0,
        'z': 0.0,
        'rot_x': 0.0,
        'rot_y': 0.0,
        'rot_z': 0.0,
        'rot_w': 0.0,
    };
    scene.add(moving_sphere);
    console.log(moving_sphere);
}

function add_ground(size_x, size_y, size_z, x, y, z, r) {
    var geometry = new THREE.BoxGeometry(size_x*2, size_y*2, size_z*2);
    var groundTexture = undefined;
    if (parseInt(size_z) >= 7000){
        groundTexture = new THREE.ImageUtils.loadTexture( 'static/img/danger.jpg' );
        groundTexture.repeat.set( 25, 25 );
    }
    else{
        groundTexture = new THREE.ImageUtils.loadTexture( 'static/img/panel35.jpg' );
        groundTexture.repeat.set( 10, 10 );
    }
    size_z = parseInt(size_z)
    groundTexture.wrapS = groundTexture.wrapT = THREE.RepeatWrapping;
    var groundMaterial = new THREE.MeshPhongMaterial( { map: groundTexture , side: THREE.DoubleSide } );
    var ground = new THREE.Mesh( geometry, groundMaterial );
    ground.position.set(x, y, z);
    ground.rotation.y = r;
    scene.add(ground);
}


function add_ramp(size_x, size_y, size_z, x, y, z, r) {
    var geometry = new THREE.BoxGeometry(size_x*2, size_y*2, size_z*2);
    var rampTexture = new THREE.ImageUtils.loadTexture( 'static/img/panel35.jpg' );
    rampTexture.wrapS = rampTexture.wrapT = THREE.RepeatWrapping;
    rampTexture.repeat.set( 10, 10 );
    var rampMaterial = new THREE.MeshPhongMaterial( { map: rampTexture , side: THREE.DoubleSide } );
    var ramp = new THREE.Mesh( geometry, rampMaterial );
    ramp.position.set(x, y , z);
    ramp.rotation.x = r;
    scene.add(ramp); 
}

function add_wall(sc_x, sc_y, sc_z, x, y, z, r) {
    var muro = objects[3].ref.clone();
    muro.children[0].material = muro.children[0].material.clone();
    muro.scale.set(sc_x, sc_y, sc_z)
    muro.position.set(x, y, z);
    muro.rotation.y = r;

    //console.log(sc_x);

    //floorTexture.wrapS = floorTexture.wrapT = THREE.RepeatWrapping;
    //floorTexture.repeat.set( 10, 10 );

    if (posters.length > 0) {
        var texture_name = posters[Math.floor(Math.random()*posters.length)];
        console.log(texture_name);
        var posterTexture = new THREE.ImageUtils.loadTexture( texture_name );
        posterTexture.needsUpdate = true;
        var posterMaterial = new THREE.MeshBasicMaterial( { map: posterTexture, side: THREE.DoubleSide} );
        //var posterMaterial = new THREE.MeshPhongMaterial( { color: 0xff0000, side: THREE.DoubleSide } );
        var posterGeometry = new THREE.PlaneGeometry(200, 250);
        var poster = new THREE.Mesh(posterGeometry, posterMaterial);
        poster.position.set(parseInt(x), parseInt(y), parseInt(z));
        poster.rotation.y = parseFloat(r);
        //console.log(poster.rotation.y);
    if (sc_x == 200) {
            if (poster.rotation.y < 0) {
                poster.position.x -= 48;
        }
        else {
                poster.position.z += 48;
        }
    }
    else {
            if (poster.rotation.y < 0) {
                poster.position.x -= 25;
        }
        else {
                poster.position.z += 25;
        }
        }
        poster.position.y += 50;
        //console.log(poster);
        scene.add(poster);
    }
    //muro.receiveShadow = true;
    //muro.castShadow = true;
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
    player.hud.innerHTML = player.name_and_energy + ' | ' + player.bonus + ' | speed: ' + player.ws['velocity'] + 'Km/H';
}

function go_fullscreen() {
    // console.log('go_fullscreen');

    if (!THREEx.FullScreen.activated()) {
        THREEx.FullScreen.request(document.getElementById('ThreeJS'));
    }
}

function loadObjects3d(objects3d, index, manager){
    if (index >= objects3d.length){
        objects[0].useQuaternion = true;
        objects[3].ref.children[0].material.transparent = true;
        // objects[3].ref.frustumCulled = false;
        start_websocket();
        return;
    }

    var texture = undefined;

    if (objects3d[index].texture != undefined){
        texture = new THREE.Texture();

        var image_loader = new THREE.ImageLoader(manager);
        image_loader.load(objects3d[index].texture, function (image) {
            texture.image = image;
            texture.needsUpdate = true;
        });
    }

    var obj_loader = new THREE.OBJLoader(manager);
    obj_loader.load(objects3d[index].object, function (object){
        object.traverse(function (child) {
            if (child instanceof THREE.Mesh) {
                if (texture) {
                    child.material.map = texture;
                }
                else {
                    child.material.color.setHex(objects3d[index].color);
                }
            }
        });
        object.children[0].geometry.computeFaceNormals();
        var geometry = object.children[0].geometry;
        THREE.GeometryUtils.center(geometry);

        objects3d[index].ref = object;
        loadObjects3d(objects3d, ++index, manager);
    });
}

function start_websocket(){
    ws = new WebSocket('ws://' + window.location.host + '/robotab');
    ws.onopen = start_the_world;
    ws.onmessage = ws_recv;
    ws.onclose = function() {
        alert('connection closed');
    }
    ws.onerror = function(e) {
        alert('ERROR');
    }
}

function create_element(el_type, id, className, onclick, innerHTML){
    var element = document.createElement(el_type);
    element.id = id;
    element.className = className;
    element.onclick = onclick;
    element.innerHTML = innerHTML;
    return element;
}

function create_and_append_elements_to_father(el_list, father_id){
    var father = document.getElementById(father_id);
    for (i in el_list){
        var el = create_element(el_list[i][0], el_list[i][1], el_list[i][2], el_list[i][3], el_list[i][4]);
        father.appendChild(el);
    }
}

function add_camera_focus(){
    var focus = [
        ['div', 'zoom-in' , 'zoom unselectable', move_back_camera_in , '+'],
        ['div', 'zoom-out', 'zoom unselectable', move_back_camera_out, '-']
    ];
    create_and_append_elements_to_father(focus, 'arrows');
}

function add_eagle_camera_arrows(){
    var directional_arrows = [
        ['div', 'arrow-top'  , 'arrow unselectable', move_eagle_camera_up   , ''],
        ['div', 'arrow-left' , 'arrow unselectable', move_eagle_camera_left , ''],
        ['div', 'arrow-right', 'arrow unselectable', move_eagle_camera_right, ''],
        ['div', 'arrow-bot'  , 'arrow unselectable', move_eagle_camera_down , '']
    ];
    create_and_append_elements_to_father(directional_arrows, 'arrows');
}

function remove_eagle_camera_arrows(){
    var directional_arrows_ids = ['arrow-top', 'arrow-left', 'arrow-right', 'arrow-bot'];
    for (i in directional_arrows_ids){
        document.getElementById(directional_arrows_ids[i]).remove();
    }
}

function move_eagle_camera_up(){
    eagleCamera.position.z -= 50;
}

function move_eagle_camera_down(){
    eagleCamera.position.z += 50;
}

function move_eagle_camera_left(){
    eagleCamera.position.x -= 50;
}

function move_eagle_camera_right(){
    eagleCamera.position.x += 50;
}

function move_eagle_camera_in(){
    if (eagleCamera.position.y >= 500){
        eagleCamera.position.y -= 100;
    }
}

function move_eagle_camera_out(){
    eagleCamera.position.y += 100;
}

function move_back_camera_in(){
    if (backCamera.position.z < -80){
        backCamera.position.z += 10;
        raycaster.far -= 50;
    }
}

function move_back_camera_out(){
    backCamera.position.z -= 10;
    raycaster.far += 50;
}

function game_over(h2_class, text){
    var div = [
        ['div', 'game_over', '', '', '']
    ];

    var h2 = [
        ['h2', '', h2_class, '', text]
    ];

    create_and_append_elements_to_father(div, 'ThreeJS');
    create_and_append_elements_to_father(h2, 'game_over');
}
