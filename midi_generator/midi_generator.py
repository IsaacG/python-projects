#!/usr/bin/python2
import midi

def NotePair(ticks, pitch, velocity):
  on = midi.NoteOnEvent(tick=0, pitch=pitch, velocity=velocity)
  off = midi.NoteOffEvent(tick=ticks, pitch=pitch)
  return on, off

def PatternFromNotes(events, instrument=26, title='Foo'):
  # Instantiate a MIDI Pattern (contains a list of tracks)
  pattern = midi.Pattern()
  # Instantiate a MIDI Track (contains a list of MIDI events)
  track = midi.Track()
  # Append the track to the pattern
  pattern.append(track)

  # Add some title text
  title = title + '\0'
  midi.ProgramNameEvent(tick=0, text=title),

  # Set the instrument
  track.append(midi.ProgramChangeEvent(tick=0, value=instrument))

  for event in events:
    track.append(event)

  # Mark the end of the track
  track.append(midi.EndOfTrackEvent(tick=0))

  return pattern


def main():
  data = {
    'Email': (43, [ # Cello
      ( 0, 65, 40),
      (80, 68, 80),
      (60, 65, 0),
      (30, 71, 60),
      (30, 68, 0),
      (30, 74, 40),
      (30, 71, 0),
      (00, 74, 0),
    ]),
    'SMS': (74, [ # Flute
      (  0, 90, 120),
      (200, 90, 0),
      (200, 93, 100),
      (200, 93, 0),
      (200, 96, 80),
      (300, 96, 0),
    ]),
    'CorpEmail': (115, [ # Steel drum
      (  0, 65, 100),
      (100, 65, 0),
      (  0, 71, 100),
      (100, 71, 0),
      (  0, 65, 100),
      (100, 65, 0),
      (  0, 59, 100),
      (100, 59, 0),
    ]),
    'Calendar': (12, [ # Vibraphone
      (  0, 85, 120),
      (200, 71, 80),
      (100, 85, 0),
      (300, 71, 0),
    ]),
  }

  for item in data:
    instrument, tpv = data[item]
    notes = [midi.NoteOnEvent(tick=t, pitch=p, velocity=v) for t, p, v in tpv]
    pattern = PatternFromNotes(notes, instrument=instrument, title=item)

    # Save the pattern to disk
    midi.write_midifile(item + ".mid", pattern)

main()
