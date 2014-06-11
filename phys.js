	var boxes = {}
	var ARENA_WIDTH = 640;
	var ARENA_HEIGHT = 480;

    	renderer = new THREE.WebGLRenderer({antialias: true});
    	renderer.setSize(ARENA_WIDTH, ARENA_HEIGHT);

	console.log(renderer);

    	container = document.getElementById("ThreeJS");
    	container.appendChild(renderer.domElement);

	var scene = new THREE.Scene();
	var keyboard = new THREEx.KeyboardState();

	console.log(scene);

        var camera = new THREE.PerspectiveCamera(45, ARENA_WIDTH / ARENA_HEIGHT, 0.1, 10000);
	camera.position.z = 2000;
	var controls = new THREE.OrbitControls( camera );
	controls.addEventListener( 'change', render );
	console.log(controls);

	// add subtle blue ambient lighting
      //var ambientLight = new THREE.AmbientLight(0x000044);
      //scene.add(ambientLight);
	/*
        camera.lookAt(scene.position);
    	camera.position.x = 0;
    	camera.position.y = 50;
    	camera.position.z = 0;
    	camera.rotation.x = -Math.PI/2;
    	scene.add(camera);
	*/


	var floorMaterial = new THREE.MeshBasicMaterial( { color: 'green' } );
    	var floorGeometry = new THREE.PlaneGeometry(2000, 2000);
    	var floor = new THREE.Mesh(floorGeometry, floorMaterial);
	floor.rotation.x = - Math.PI / 2;
	floor.position.y = 0;
	floor.position.x = 0;
	floor.position.z = 0;

	scene.add(floor);

	var texture = THREE.ImageUtils.loadTexture( 'crate.gif');

        var ws = new WebSocket('ws://localhost:9090/phys');
        ws.onmessage = function(e) {
                //console.log(e.data);
                var items = e.data.split(':')
                var box = items[0];
                //console.log(box);
                var params = items[1].split(',');
                if (!(box in boxes)) {
			var material = new THREE.MeshBasicMaterial( { map: texture});
                        var new_box = new THREE.Mesh(new THREE.BoxGeometry(parseInt(params[3]), parseInt(params[4]), parseInt(params[5])), material);
			scene.add(new_box);
			THREE.GeometryUtils.center(new_box.geometry);
			boxes[box] = new_box;
			console.log(new_box);
                }

		var my_box = boxes[box];
		my_box.rotation.x = parseFloat(params[6]);
		my_box.rotation.y = parseFloat(params[7]);
		my_box.rotation.z = parseFloat(params[8]);
		my_box.position.x = parseInt(params[0]);
		my_box.position.y = parseInt(params[1]);
		my_box.position.z = parseInt(params[2]);
        };

	animate();

	function animate() {
    		setTimeout( function() {
        		requestAnimationFrame( animate );
    		}, 1000 / 30 );
    		render();
    		update();
	}

function render() {
	renderer.render(scene, camera);
}

function update() {
	//cube.rotation.x += 0.005;
	//cube.rotation.y += 0.01;
	if (keyboard.pressed("w")) {
		console.log('fw');
		ws.send('fw');
	}
}

