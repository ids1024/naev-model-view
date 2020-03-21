#!/usr/bin/env python3

# TODO: antialias edges of model
# TODO: diffuse
# TODO: file format: interleaved, extendable
# TODO: uniform buffer object
# TODO: https://stackoverflow.com/questions/50806126/why-are-textures-displayed-incorrectly-when-using-indexed-rendering-gldraweleme
# TODO: handle material switches within one object (combine into atlas texture? texture array? multiple draws?)
# TODO: bump map
# TODO: specral, emit, l (used in peacemaker.obj?)
# https://people.cs.clemson.edu/~dhouse/courses/405/docs/brief-mtl-file-format.html
# illum 2 is Blinn–Phong reflection model
# map files in a .mtl are square power of two
# TODO: make sure bump mapping is correct

import sys
import os
import time
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.arrays.vbo import VBO
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
import glm
import math
import argparse

vert = """
#version 150

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
#version 150

uniform sampler2D map_Kd, map_Bump;

uniform vec3 Ka, Kd;
uniform float d, bm;

in vec2 tex_out;
in vec3 normal_out;
out vec4 color_out;

const vec3 lightDir = vec3(0, 0, -1);

void main(void) {
   vec3 norm = normalize(normal_out + bm * texture(map_Bump, tex_out).xyz);

   vec3 ambient = Ka;

   vec3 diffuse = Kd * max(dot(norm, lightDir), 0.0);

   color_out = texture(map_Kd, tex_out);
   color_out.rgb *= .4 * ambient + .7 * diffuse;
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
    bm = 1
    d = 1.0

    def __init__(self):
       self.map_Kd = solidTexture(1, 1, 1)
       self.map_Bump = solidTexture(0, 0, 0)


def mtl_getopt(args, arg_spec):
    results = {}

    i = 0
    while i < len(args):
        matched = False
        if args[i].startswith('-'):
            for name, count in arg_spec.items(): 
                if args[i][1:] == name:
                    results[name] = tuple(args[i+1:i+count+1])
                    i += count
                    matched = True
        if not matched:
            break
        i += 1

    return (results, tuple(args[i:]))


def parse_mtl(path):
    f = open(path)

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
            pass
        elif l[0] == 'map_Kd':
            # XXX handle s
            opts, rest = mtl_getopt(l[1:], {'s': 3})
            map_Kd = ' '.join(rest)
            cur_material.map_Kd = loadTexture(os.path.dirname(path) + '/' + map_Kd)
        elif l[0] == 'map_Bump':
            # XXX handle s
            opts, rest = mtl_getopt(l[1:], {'s': 3, 'bm': 1})
            cur_material.bm = float(opts['bm'][0])
            map_Bump = ' '.join(rest)
            cur_material.map_Bump = loadTexture(os.path.dirname(path) + '/' + map_Bump)
        else:
            print(f"Ignoring {l[0]}")

    return materials


class Object:
    def __init__(self):
        self.vertices = []
        self.mtl_list = []


class Object_C:
    def __init__(self, o):
        assert isinstance(o, Object)
        self.vertices = (GLfloat * len(o.vertices))(*o.vertices)
        self.mtl_list = o.mtl_list


class Object_VBO:
    def __init__(self, o):
        assert isinstance(o, Object_C)

        self.vertices = VBO(o.vertices, GL_STATIC_DRAW, GL_ARRAY_BUFFER)
        self.vao = glGenVertexArrays(1)
        self.mtl_list = o.mtl_list

        glBindVertexArray(self.vao)

        self.vertices.bind()

        vertex_attrib = glGetAttribLocation(glsl_program, "vertex")
        glEnableVertexAttribArray(vertex_attrib)
        glVertexAttribPointer(vertex_attrib, 3, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(0))

        tex_attrib = glGetAttribLocation(glsl_program, "tex")
        glEnableVertexAttribArray(tex_attrib)
        glVertexAttribPointer(tex_attrib, 2, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(3 * 4))

        normal_attrib = glGetAttribLocation(glsl_program, "normal")
        glEnableVertexAttribArray(normal_attrib)
        glVertexAttribPointer(normal_attrib, 2, GL_FLOAT, GL_FALSE, 8 * 4, c_void_p(5 * 4))


    def draw(self):
        glBindVertexArray(self.vao)

        scale = 1/6

        if window_width < window_height:
            scale_w = scale
            scale_h = scale_w * (window_width / window_height)
        else:
            scale_h = scale
            scale_w = scale_h * (window_height / window_width)

        trans_unif = glGetUniformLocation(glsl_program, "trans")
        trans = glm.ortho(-1, 1, -1, 1)
        trans = glm.scale(trans, glm.vec3(scale_w, scale_h, scale))
        trans = glm.rotate(trans, -math.pi / 2, glm.vec3(1, 0, 0))
        trans = glm.rotate(trans, math.pi / 4, glm.vec3(1, 0, 0))
        trans = glm.rotate(trans, rot, glm.vec3(0, 0, 1))
        glUniformMatrix4fv(trans_unif, 1, GL_FALSE, trans.to_list())

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)

        glUniform1i(glGetUniformLocation(glsl_program, "map_Kd"), 0)
        glUniform1i(glGetUniformLocation(glsl_program, "map_Bump"), 1)

        for (mtl, start, count) in self.mtl_list:
            glUniform3f(glGetUniformLocation(glsl_program, "Kd"), *mtl.Kd)
            glUniform3f(glGetUniformLocation(glsl_program, "Ka"), *mtl.Ka)
            glUniform1f(glGetUniformLocation(glsl_program, "d"), mtl.d)
            glUniform1f(glGetUniformLocation(glsl_program, "bm"), mtl.bm)

            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, mtl.map_Kd)

            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, mtl.map_Bump)

            glDrawArrays(GL_TRIANGLES, start, count)

        gl_checkErr()


class Ship:
    def __init__(self, body, engine):
        self.body = body
        self.engine = engine

    def draw(self):
        self.body.draw()
        self.engine.draw()


def parse_obj(path):
    f = open(path)

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
            mtls = parse_mtl(os.path.dirname(path) + '/' + l[1])
        # Use material
        elif l[0] == 'usemtl':
            cur_object.mtl_list.append([mtls[l[1]], len(cur_object.vertices) // 8, 0])
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
            cur_object.mtl_list[-1][2] += 3
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

parser = argparse.ArgumentParser()
parser.add_argument('obj')
parser.add_argument('--rot', type=int, default=0)
parser.add_argument('--res', type=int, default=256)
parser.add_argument('--save')
args = parser.parse_args()

glutInit("")
glutInitContextVersion(3, 2)
glutInitContextProfile(GLUT_CORE_PROFILE)
glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH | GLUT_MULTISAMPLE)
glutInitWindowSize(800, 600)
glutInitWindowPosition(0, 0)
window = glutCreateWindow("Obj Viewer")

glsl_program = gl_program_vert_frag(vert, frag)
glUseProgram(glsl_program)

ship = parse_obj(args.obj)

rot = args.rot * math.pi / 180

window_width = 800
window_height = 600

if args.save is not None:
    fb = glGenFramebuffers(1)
    glBindFramebuffer(GL_FRAMEBUFFER, fb)

    color_buffer = glGenRenderbuffers(1)
    glBindRenderbuffer(GL_RENDERBUFFER, color_buffer)
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA, args.res, args.res);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, color_buffer)

    depth_buffer = glGenRenderbuffers(1)
    glBindRenderbuffer(GL_RENDERBUFFER, depth_buffer)
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, args.res, args.res)
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_buffer)

    glViewport(0, 0, args.res, args.res)
    window_height = args.res
    window_width = args.res

    glClearColor(0., 0., 0., 0.)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    ship.draw()

    data = glReadPixels(0, 0, args.res, args.res, GL_RGBA, GL_UNSIGNED_BYTE)
    image = Image.frombytes('RGBA', (args.res, args.res), data)
    image = image.transpose(Image.FLIP_TOP_BOTTOM)
    image.save(args.save)

    sys.exit()

def display():
    glClearColor(1., 1., 1., 1.)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    ship.draw()
    glutSwapBuffers()
    glutPostRedisplay()

def reshape(w, h):
    global window_width, window_height
    window_width = w
    window_height = h
    glViewport(0, 0, w, h)

def keyboard(key, x, y):
   global rot
   if key == b'a':
      rot += math.pi / 16
   elif key == b'd':
      rot -= math.pi / 16

glutDisplayFunc(display)
glutReshapeFunc(reshape)
glutKeyboardFunc(keyboard)
glutMainLoop()
