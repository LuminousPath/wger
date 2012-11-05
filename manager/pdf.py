# -*- coding: utf-8 -*-

# This file is part of Workout Manager.
# 
# Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License

import logging
import uuid
import datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _

from manager.models import DaysOfWeek
from manager.models import TrainingSchedule

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4, cm, landscape, portrait
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table
from reportlab.lib import colors

from workout_manager import get_version

logger = logging.getLogger('workout_manager.custom')

"""
PDF functions
"""

@login_required
def workout_log(request, id):
    """Generates a PDF with the contents of the given workout
    
    See also
    * http://www.blog.pythonlibrary.org/2010/09/21/reportlab-tables-creating-tables-in-pdfs-with-python/
    * http://www.reportlab.com/apis/reportlab/dev/platypus.html
    """
    
    #Load the workout
    workout = get_object_or_404(TrainingSchedule, pk=id, user=request.user)
    
    # Create the HttpResponse object with the appropriate PDF headers.
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=%s.pdf' % _('Workout')
    
    # Create the PDF object, using the response object as its "file."
    doc = SimpleDocTemplate(response,
                            pagesize = A4,
                            #pagesize = landscape(A4),
                            leftMargin = cm,
                            rightMargin = cm,
                            topMargin = 0.5 * cm,
                            bottomMargin = 0.5 * cm,
                            title = _('Workout'),
                            author = _('Workout Manager'),
                            subject = _('Workout for %s') % request.user.username)

    # container for the 'Flowable' objects
    elements = []
    
    # stylesheet
    styleSheet = getSampleStyleSheet()
    
    style = ParagraphStyle(
        name = 'Normal',
        #fontName='Helvetica-Bold',
        fontSize = 8,
        )
    
    # Set the widths and heights of rows and columns
    # TODO: if the height is set here, there is no automatic scaling when e.g.
    #       the exercise names are too long. This should be fixed, till then set
    #       to None for automatic scaling
    #rowheights = (13)
    colwidths = None
    rowheights = None
    
    
    # table data, here we will put the workout info
    data = []
    
    
    # Init several counters and markers, this will be used after the iteration to
    # set different borders and colours
    day_markers = []
    exercise_markers = {}
    group_exercise_marker = {}
    group_day_marker = {}
    
    # Set the number of weeks for this workout
    # (sets number of columns for the weight/date log)
    nr_of_weeks = 7
    
    # Set the first column of the weight log, depends on design
    first_weight_column = 3
    
    # Background colour for days
    # Reportlab doesn't use the HTML hexadecimal format, but has a range of
    # 0 till 1, so we have to convert here.
    header_colour = colors.Color(int('73', 16) / 255.0,
                                 int('8a', 16) / 255.0,
                                 int('5f', 16) / 255.0)
    
    
    #
    # Iterate through the Workout
    #
    
    # Days
    for day in workout.day_set.select_related():
        set_count = 1
        day_markers.append(len(data))
        group_day_marker[day.id] = {'start': len(data), 'end': len(data)}
        
        if not exercise_markers.get(day.id):
            exercise_markers[day.id] = []
        
        days_of_week = [_(day_of_week.day_of_week) for day_of_week in day.day.select_related()]
        
        P = Paragraph('<para align="center">%(days)s: <strong>%(description)s</strong></para>' %
                                        {'days' : ', '.join(days_of_week),
                                         'description': day.description},
                      styleSheet["Normal"])
        
        data.append([P])
        
        # Note: the _('Date') will be on the 3rd cell, but since we make a span
        #       over 3 cells, the value has to be on the 1st one
        data.append([_('Date') + ' ', '', ''] + [''] * nr_of_weeks)
        data.append([_('Nr.'), _('Exercise'), _('Reps')] + [_('Weight')] * nr_of_weeks)
        
        # Sets
        for set_obj in day.set_set.select_related():
            group_exercise_marker[set_obj.id] = {'start': len(data), 'end': len(data)}
            
            # Exercises
            for exercise in set_obj.exercises.select_related():
                
                group_exercise_marker[set_obj.id]['end'] = len(data)
                
                exercise_markers[day.id].append(len(data))
                setting_data = []
                
                
                # Settings
                for setting in exercise.setting_set.filter(set_id = set_obj.id):
                    if setting.reps == 99:
                        repetitions = '∞'
                    else:
                        repetitions = str(setting.reps)
                    setting_data.append(repetitions)
                    

                # If there are more than 1 settings, don't output the repetitions
                # e.g. "4 x 8 8 10 10" is shown only as "8 8 10 10", after all
                # those 4 sets are not done four times!
                if len(setting_data) == 0:
                    out = '' # nothing set
                    
                elif len(setting_data) == 1:
                    out = str(set_obj.sets) + ' × ' + setting_data[0]
                    
                elif len(setting_data) > 1:
                    out = ', '.join(setting_data)
                
                data.append([set_count, Paragraph(exercise.name, style), out] + [''] * nr_of_weeks)
            set_count += 1
        
        # Note: as above with _('Date'), the _('Impression') has to be here on
        #       the 1st cell so it is shown after adding a span
        #data.append([_('Impression'), '', ''])
        
        set_count += 1
        group_day_marker[day.id]['end'] =  len(data)
        
        #data.append([''])
    
    # Set general table styles
    table_style = [
                    ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                    ('BOX', (0,0), (-1,-1), 1.25, colors.black),
                    ('FONT', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('VALIGN',(0, 0),(-1, -1),'MIDDLE'),
                    
                    #Note: a padding of 3 seems to be the default
                    ('LEFTPADDING', (0, 0), (-1, -1), 2), 
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                   ]
    
    # Set specific styles, e.g. background for title cells
    previous_marker = 0
    for marker in day_markers:
        # Set background colour for headings
        table_style.append(('BACKGROUND', (0, marker), (-1, marker), header_colour))
        table_style.append(('BOX', (0, marker), (-1, marker), 1.25, colors.black))
        table_style.append(('BOX', (0, marker), (-1, marker + 2), 1.25, colors.black))
        
        # Make the headings span the whole width
        table_style.append(('SPAN', (0, marker), (-1, marker)))
        
        # Make the date span 3 cells and align it to the right
        table_style.append(('ALIGN', (0, marker + 1), (2, marker +1), 'RIGHT'))
        table_style.append(('SPAN', (0, marker +1), (2, marker + 1)))
        

    # Combine the cells for exercises on the same set
    for marker in group_exercise_marker:
        start_marker = group_exercise_marker[marker]['start']
        end_marker = group_exercise_marker[marker]['end']
        
        table_style.append(('VALIGN',(0, start_marker),(0, end_marker),'MIDDLE'))
        table_style.append(('SPAN', (0, start_marker), (0, end_marker)))
    
    # Set an alternating background colour for rows
    for i in exercise_markers:
        counter = 1
        for j in exercise_markers[i]:
            if not j % 2:
                table_style.append(('BACKGROUND', (1, j -1), (-1, j -1), colors.lavender))
            counter += 1
    
    
    # Make the 'impression' span 3 cells and align it to the right
    for marker in group_day_marker:
        start_marker = group_day_marker[marker]['start']
        end_marker = group_day_marker[marker]['end']
        
        #table_style.append(('ALIGN', (0, end_marker - 2), (2, end_marker - 2), 'RIGHT'))
    
    #  TODO: this only makes sense if the "empty" cells can be made less high
    #       than the others, otherwise it takes too much space!
    # Draw borders and grids around the daystable_style.append(('SPAN', (0, end_marker - 2), (2, end_marker - 2)))
    #    
    #    table_style.append(('INNERGRID', (0, start_marker), (-1,end_marker -2 ), 0.25, colors.black))
    #    table_style.append(('BOX', (0, start_marker), (-1, end_marker -2), 1.25, colors.black))
        
    
    # Set the table data
    if data:
        t = Table(data, colwidths, rowheights, style = table_style)
        
        # Manually set the width of the columns
        for i in range(first_weight_column, nr_of_weeks + first_weight_column):
            t._argW[i] = 1.8 * cm # Columns for entering the log
            
        t._argW[0] = 0.6 * cm # Exercise numbering
        t._argW[1] = 3.5 * cm # Name of exercise
        t._argW[2] = 1.9 * cm # Repetitions
    
    # There is nothing to output
    else:
        t = Paragraph(_('<i>This is an empty workout, what did you expect on the PDF?</i>'),
                      styleSheet["Normal"])

    #
    # Add all elements to the document
    # 
    
    # Set the title (if available)
    if workout.comment:
        P = Paragraph('<para align="center"><strong>%(description)s</strong></para>' %
                                            {'description' : workout.comment},
                          styleSheet["Normal"])
        elements.append(P)
    
        # Filler
        P = Paragraph('<para> </para>', styleSheet["Normal"])
        elements.append(P)

    # Append the table
    elements.append(t)
    
    # Footer, add filler paragraph
    P = Paragraph('<para> </para>', styleSheet["Normal"])
    elements.append(P)
    
    # Print date and info
    P = Paragraph('<para align="left">%(date)s - %(created)s v%(version)s</para>' %
                    {'date' : _("Created on the <b>%s</b>") % workout.creation_date.strftime("%d.%m.%Y"),
                     'created' : "Workout Manager",
                     'version': get_version()},
                  styleSheet["Normal"])
    elements.append(P)
    

    # write the document and send the response to the browser
    doc.build(elements)

    return response