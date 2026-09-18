# One FRAME from whatever detector runs on the vehicle.
#
# The contract between a seabed detector and robot_mind_seabed's search node.
# One message PER FRAME, not per detection: a detector that scores nothing on
# a frame still publishes it with score 0.0, because a look that saw nothing
# is evidence of absence and a missing message is not. The node aggregates
# frames into looks at cells itself; it never sees an image.

std_msgs/Header header        # stamp = the frame's time
string frame_id               # the frame file name or sequence number
string cls                    # what the detector calls it ("vegetation", "anomaly", ...)
float32 score                 # the detector's own number in [0, 1]; 0.0 = looked, saw nothing
float32 altitude_m            # DVL altitude at the frame (NaN if unknown)
string visibility_class       # "bed_resolved" | "bed_veiled" | "water_column_only" | ""
geometry_msgs/Point position  # vehicle position at the frame, local metres (north = y, east = x, depth = z)
string source                 # detector tag (model id, version)
bool ok                       # false = the detector could not score this frame (no claim is made)
