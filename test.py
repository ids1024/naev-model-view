# TODO: antialias edges of model
# TODO: diffuse
# TODO: file format: interleaved, extendable
# TODO: uniform buffer object
# TODO: https://stackoverflow.com/questions/50806126/why-are-textures-displayed-incorrectly-when-using-indexed-rendering-gldraweleme
# TODO: handle material switches within one object (combine into atlas texture? texture array? multiple draws?)

import sys
import time
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.arrays.vbo import VBO
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
import glm
import math

vert = """
#version 130

uniform mat4 trans;

in vec4 vertex;
in vec3 normal;
in vec2 tex;
out vec2 tex_out;
out vec3 normal_out;

void main(void) {
   tex_out = tex;
   normal_out = (trans * vec4(normal, 1.)).xyz;
   gl_Position = trans * vertex;
}
"""


frag = """
#version 130

uniform sampler2D map_Kd;
uniform vec3 Ka;
uniform vec3 Kd;
uniform float d;

in vec2 tex_out;
in vec3 normal_out;
out vec4 color_out;

void main(void) {
   vec3 norm = normalize(normal_out);
   vec3 lightDir = normalize(vec3(1, 0, 0) - gl_FragCoord.xyz);
   float diff = max(dot(norm, lightDir), 0.0);

   color_out = texture(map_Kd, tex_out);
   color_out.rgb *= Kd * diff;
   color_out.rgb = color_out.rgb * .9 + Ka * .1;
   color_out.a = d;
}
"""


def loadTexture(path):
    image = Image.open(path).convert("RGB")

    image = image.transpose(Image.FLIP_TOP_BOTTOM)

    texid = glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, texid)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height,
                 0, GL_RGB, GL_UNSIGNED_BYTE, image.tobytes())

    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

    return texid


def solidTexture(r, g, b):
    texid = glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, texid)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 1, 1,
                 0, GL_RGB, GL_FLOAT, [r, g, b])

    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)

    return texid


def gl_checkErr():
    err = glGetError()
    if err != 0:
        print(gluErrorString(err))


def gl_program_vert_frag(vert, frag):
   vertex_shader = compileShader(vert, GL_VERTEX_SHADER)
   fragment_shader = compileShader(frag, GL_FRAGMENT_SHADER)
   return compileProgram(vertex_shader, fragment_shader)


class Material:
    Ka = None
    Kd = None
    Ks = None
    Ns = None
    Ni = None
    d = 1.0

    def __init__(self):
       self.map_Kd = solidTexture(1, 1, 1)


def parse_mtl(f):
    materials = {}
    cur_material = None

    for l in f:
        l = l.split()
        if not l or l[0].startswith('#'):
            continue

        if l[0] == 'newmtl':
            m = Material()
            materials[l[1]] = m
            cur_material = m
        # Ambient
        elif l[0] == 'Ka':
            cur_material.Ka = tuple(float(i) for i in l[1:4])
        # Diffuse
        elif l[0] == 'Kd':
            cur_material.Kd = tuple(float(i) for i in l[1:4])
        # Specular
        elif l[0] == 'Ks':
            cur_material.Ks = tuple(float(i) for i in l[1:4])
        elif l[0] == 'Ns':
            cur_material.Ns = float(l[1])
        elif l[0] == 'Ni':
            cur_material.Ni = float(l[1])
        elif l[0] == 'd':
            cur_material.d = float(l[1])
        # Illumination mode
        elif l[0] == 'illum':
            cur_material.d = int(l[1])
        elif l[0] == 'map_Kd':
            cur_material.map_Kd = loadTexture(l[1])
        else:
            print(f"Ignoring {l[0]}")

    return materials


class Object:
    mtl = None
    def __init__(self):
        self.vertices = []


class Object_C:
    def __init__(self, o):
        assert isinstance(o, Object)
        self.vertices = (GLfloat * len(o.vertices))(*o.vertices)
        self.mtl = o.mtl


class Object_VBO:
    def __init__(self, o):
        assert isinstance(o, Object_C)
        self.vertices = VBO(o.vertices, GL_STATIC_DRAW, GL_ARRAY_BUFFER)
        self.mtl = o.mtl

    def draw(self):
        self.vertices.bind()

        vertex_attrib = glGetAttribLocation(glsl_program, "vertex")
        glEnableVertexAttribArray(vertex_attrib)
        glVertexAttribPointer(vertex_attrib, 3, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(0));

        tex_attrib = glGetAttribLocation(glsl_program, "tex")
        glEnableVertexAttribArray(tex_attrib)
        glVertexAttribPointer(tex_attrib, 2, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(3 * 4));

        normal_attrib = glGetAttribLocation(glsl_program, "normal")
        glEnableVertexAttribArray(normal_attrib)
        glVertexAttribPointer(normal_attrib, 2, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(5 * 4));

        trans_unif = glGetUniformLocation(glsl_program, "trans")
        rot = time.time() / 4 % 2*math.pi
        trans = glm.ortho(-1, 1, -1, 1)
        trans = glm.scale(trans, glm.vec3(1/6, 1/6, 1/6))
        trans = glm.rotate(trans, -math.pi / 2, glm.vec3(1, 0, 0))
        trans = glm.rotate(trans, math.pi / 4, glm.vec3(1, 0, 0))
        trans = glm.rotate(trans, rot, glm.vec3(0, 0, 1))

        glUniformMatrix4fv(trans_unif, 1, GL_FALSE, trans.to_list());

        glUniform3f(glGetUniformLocation(glsl_program, "Kd"), *self.mtl.Kd)
        glUniform3f(glGetUniformLocation(glsl_program, "Ka"), *self.mtl.Ka)

        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, self.mtl.map_Kd)
        glUniform1i(glGetUniformLocation(glsl_program, "map_Kd"), 0);

        glUniform1f(glGetUniformLocation(glsl_program, "d"), self.mtl.d)

        # XXX
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)

        #glEnable(GL_CULL_FACE);
        #glCullFace(GL_BACK);

        count = self.vertices.data._length_ // 3
        glDrawArrays(GL_TRIANGLES, 0, count)
        gl_checkErr()


class Ship:
    def __init__(self, body, engine):
        self.body = body
        self.engine = engine

    def draw(self):
        self.body.draw()
        self.engine.draw()


def parse_obj(f):
    engine = Object()
    body = Object()
    cur_object = None
    mtls = None

    v_list = []
    vt_list = []
    vn_list = []

    for l in f:
        l = l.split()
        if not l or l[0].startswith('#'):
            continue

        # Load materials from file
        if l[0] == 'mtllib':
            with open(l[1]) as f:
                mtls = parse_mtl(f)
        # Use material
        elif l[0] == 'usemtl':
            cur_object.mtl = mtls[l[1]]
        # Smoothing
        elif l[0] == 's':
            pass
        # Face
        elif l[0] == 'f':
            for i in l[1:4]:
                v, vt, vn = (int(j or 0) for j in i.split('/'))
                cur_object.vertices.extend(v_list[v - 1])
                if (vt == 0):
                    cur_object.vertices.extend((0, 0))
                else:
                    cur_object.vertices.extend(vt_list[vt - 1])
                cur_object.vertices.extend(vn_list[vn - 1])
        # Vertex
        elif l[0] == 'v':
            v_list.append(tuple(float(i) for i in l[1:4]))
        # Texture vertex
        elif l[0] == 'vt':
            vt_list.append(tuple(float(i) for i in l[1:3]))
        # Vertex normal
        elif l[0] == 'vn':
            vn_list.append(tuple(float(i) for i in l[1:4]))
        # Object
        elif l[0] == 'o':
            if l[1] == 'engine':
                cur_object = engine
            elif l[1] == 'body':
                cur_object = body
            else:
                print(f"Ignoring object {l[1]}")
        else:
            print(f"Ignoring {l[0]}")

    engine = Object_C(engine)
    body = Object_C(body)

    engine = Object_VBO(engine)
    body = Object_VBO(body)

    return Ship(body, engine)


glutInit("")
glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_ALPHA | GLUT_DEPTH | GLUT_3_2_CORE_PROFILE)
glutInitWindowSize(1920, 1080)
glutInitWindowPosition(0, 0)
window = glutCreateWindow("")

with open(sys.argv[1]) as f:
    ship = parse_obj(f)

glsl_program = gl_program_vert_frag(vert, frag)
glUseProgram(glsl_program)

while True:
    glClearColor(1., 1., 1., 1.)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    ship.draw()
    glutSwapBuffers()
