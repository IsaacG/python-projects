#!/bin/python

import itertools
import json
import os
import random

DATA = os.getenv('HOME') + '/.xdg/data/dnd_dice.json'

class Value:

  def __init__(self, val):
    if isinstance(val, int):
      self.fixed = True
      self.val = val
    if isinstance(val, str):
      if 'd' in val:
        count, sides = val.split('d', 1)
        if count == '':
          count = '1'
        self.fixed = False
        self.count, self.sides = int(count), int(sides)
      else:
        self.fixed = True
        self.val = int(val)

  def roll(self):
    if self.fixed:
      self.parts = [self.val]
    else:
      self.parts = [random.randint(1, self.sides) for _ in range(self.count)]

  def int_val(self):
    return sum(self.parts)

  def __str__(self):
    if self.fixed:
      return str(self.val)
    else:
      return f"{self.count}d{self.sides}"


class Roller:

  def __init__(self):
    with open(DATA) as f:
      self.data = json.load(f)

  def resolve(self, val):
    val = self.clean(val)
    self.parts = []
    matches = [i for i in self.data if i.startswith(val)]
    if len(matches) > 1:
      return "More than one match. Cannot resolve."
    if matches:
      expanded = f'{matches} = {self.data[matches[0]]}'
      print(expanded)
      return self.resolve(self.data[matches[0]])
    else:
      if '+' in val:
        return itertools.chain.from_iterable(self.resolve(v) for v in val.split('+'))
      else:
        return [Value(val)]

  def clean(self, val):
    val = val.replace(' ', '')
    val = val.replace('-', '+-')
    val = val.replace('++', '+')
    return val

  def roll(self, val):
    parts = list(self.resolve(val))
    for p in parts:
      p.roll()
    return [
      [str(p) for p in parts],
      [p.parts for p in parts],
      sum(p.int_val() for p in parts),
    ]

