#!/usr/bin/env python3
"""Build pico-comp-viewer.html (self-contained, offline) from assembly.json.

Run FreeCADCmd case.py first. Needs npm once to fetch three.js r147 (has the
non-module builds). Open the HTML in any browser; drag to orbit, wheel to zoom.
"""
import json
import os
import subprocess
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
subprocess.run(["npm", "install", "--prefix", tmp, "three@0.147.0", "--silent"], check=True)
three = open(f"{tmp}/node_modules/three/build/three.min.js").read()
orbit = open(f"{tmp}/node_modules/three/examples/js/controls/OrbitControls.js").read()
data = open(os.path.join(here, "assembly.json")).read()

html = f"""<!doctype html><meta charset="utf-8"><title>Pico-COMP</title>
<style>body{{margin:0;background:#1b1d22;overflow:hidden;font:13px sans-serif;color:#ddd}}
#ui{{position:fixed;top:8px;left:8px;background:#0009;padding:8px;border-radius:6px}}
label{{display:block}}</style>
<div id="ui"><b>Pico-COMP</b> (drag: orbit, wheel: zoom, right-drag: pan)<div id="list"></div></div>
<script>{three}</script><script>{orbit}</script>
<script>
const parts={data};
const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,1,3000);
cam.position.set(260,230,330);
const r=new THREE.WebGLRenderer({{antialias:true}});r.setSize(innerWidth,innerHeight);
document.body.appendChild(r.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x444455,0.8));
const d=new THREE.DirectionalLight(0xffffff,0.8);d.position.set(200,400,300);scene.add(d);
const grp=new THREE.Group();scene.add(grp);
const list=document.getElementById('list');
for(const p of parts){{
  let g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(p.v,3));
  g.setIndex(p.f);g=g.toNonIndexed();g.computeVertexNormals();
  const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({{color:new THREE.Color(...p.color),side:THREE.DoubleSide,roughness:0.6}}));
  grp.add(m);
  const l=document.createElement('label'),c=document.createElement('input');
  c.type='checkbox';c.checked=true;c.onchange=()=>m.visible=c.checked;
  l.append(c,' '+p.name);list.append(l);
}}
const box=new THREE.Box3().setFromObject(grp),ctr=box.getCenter(new THREE.Vector3());
const ctl=new THREE.OrbitControls(cam,r.domElement);ctl.target.copy(ctr);ctl.update();
addEventListener('resize',()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();r.setSize(innerWidth,innerHeight)}});
(function a(){{requestAnimationFrame(a);r.render(scene,cam)}})();
</script>"""
out = os.path.join(here, "pico-comp-viewer.html")
open(out, "w").write(html)
print("wrote", out)
