# What the search node's ledger says about one cell of the survey map.
#
# never_looked  no look of the vehicle's own has answered for this cell
# cleared       an own look recorded an absence here (a certificate may cite it)
# lead          an own look saw the target here once, too faintly for the bar
# refuted       a later own look at this cell contradicted that sighting
# retired       the cell was excluded from the search (repeated or failed looks)
# found         the engine's verdict resolves the target here

string cell
string state
uint16 looks
float32 best_score
string last_look_id
int64 last_look_time
