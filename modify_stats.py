import datetime as dt

def move_leaderboards():
    pass

def merge_leaderboards(src_steps, dest_steps):
    src_list = src_steps.find('HighScoreList')
    dest_list = dest_steps.find('HighScoreList')
    def find(key):
        return src_list.find(key), dest_list.find(key)
    
    def parse_dt(text):
        return dt.datetime.strptime(text, "%Y-%m-%d")

    # numplayed += other
    s,d = find('NumTimesPlayed')
    d.text = str(int(s.text) + int(d.text))

    # lastplayed = max
    s,d = find('LastPlayed')
    d.text = max(parse_dt(s.text), parse_dt(d.text)).strftime('%Y-%m-%d')

    # highgrade = max (take smallest tier)
    s,d = find('HighGrade')
    d.text = min(s.text, d.text, key=lambda s: int(s[4:]))

    # highscore - merge, sort descending by PrecentDP, take top 10
    highscores = [
        *src_list.findall('HighScore'),
        *dest_list.findall('HighScore')
    ]
    highscores.sort(key=lambda x: float(x.find('PercentDP').text), reverse=True)
    highscores = highscores[:10]

    for x in dest_list.findall('HighScore'):
        dest_list.remove(x)
    for x in highscores:
        dest_list.append(x)

# to fix couples stats:
# go by note count?
    
# just delete these scores:
# itg! Rhythm is just a step away v0.80
# untitled stream pack
[
 ('Couples Boot Camp/3y3s (JMBS FUNKOT RMX)/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/B.B.K.K.B.K.K/', 'dance-double', 'Challenge'),'Beginner',
 ('Couples Boot Camp/BREAKNECK NYAN! NYAN!/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Claidheamh Soluis/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Dharma/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Everything but the Girl/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Finale/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Gekiatsu Majiyaba Cheergirl/',
  'dance-double',
  'Challenge'), 'Beginner',
 ('Couples Boot Camp/Genesis At Oasis (Hirayasu Matsudo Remix)/',
  'dance-double',
  'Challenge'), 'Beginner',
 ('Couples Boot Camp/Ha-le-lu-jah/', 'dance-double', 'Challenge'), 'Beginner',
 ('Couples Boot Camp/Luminous Days/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Mind Mapping(ag Remix)/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Mirai Prism/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Nanairo Light/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Prominence/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Rot in hell!!/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/SO FLY ME TO YOU/', 'dance-double', 'Challenge'),  'Beginner',
 ('Couples Boot Camp/Take to Lips/', 'dance-double', 'Challenge'),  'Beginner',
 ('Only One Couples Pack 2/Call Me Maybe/', 'dance-double', 'Hard'),  'Beginner',
 ('Only One Couples Pack 2/Drive Me Crazy/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 2/Face/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 2/Icarus/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 2/Mr Taxi/', 'dance-double', 'Challenge'), 'Easy',
 ('Only One Couples Pack 2/Spring of Life/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 3/Flow In Da Sky/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 3/For You/', 'dance-double', 'Challenge'),  'Easy',
 ('Only One Couples Pack 3/I Knew You Were Trouble/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 3/Longing Back/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 4/Alive/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 4/Invoker/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack 4/Party/', 'dance-double', 'Challenge'),  'Beginner',
 ('Only One Couples Pack/Bangarang/', 'dance-double', 'Hard'), 'Beginner',
 ('Only One Couples Pack/Bubble Pop/', 'dance-double', 'Challenge'),  'Beginner',
 ('Only One Couples Pack/Jounetsu no Wobble/', 'dance-double', 'Hard'), 'Beginner',
 ("Only One Couples Pack/PONPONPON (Twintale's Hardcore Bootleg Mix)/",
  'dance-double',
  'Hard'), 'Beginner',
 ('Only One Couples Pack/Pop Culture/', 'dance-double', 'Hard'),  'Beginner']
    