{%load commitfest%}
<tr>
 <th>Emails</th>
 <td>
  <dl>
   {%for t in patch.mailthread_set.all%}
    <dt style="white-space: nowrap;"><a href="https://www.postgresql.org/message-id/flat/{{t.messageid}}">{{t.subject}}</a> <button type="button" class="close close-nofloat" title="Detach this thread" onclick="detachThread({{cf.id}},{{patch.id}},'{{t.messageid}}')">&times;</button></dt>
    <dd>
     First at <a href="https://www.postgresql.org/message-id/{{t.messageid}}">{{t.firstmessage}}</a> by {{t.firstauthor|hidemail}}<br/>
     Latest at <a href="https://www.postgresql.org/message-id/{{t.latestmsgid}}">{{t.latestmessage}}</a> by {{t.latestauthor|hidemail}}<br/>
     {%for ta in t.mailthreadattachment_set.all%}
      {%if forloop.first%}
       Latest attachment (<a href="https://www.postgresql.org/message-id/attachment/{{ta.attachmentid}}/{{ta.filename}}">{{ta.filename}}</a>) at <a href="https://www.postgresql.org/message-id/{{ta.messageid}}">{{ta.date}}</a> from {{ta.author|hidemail}} <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-target="#att{{t.pk}}" title="Show all attachments"><i class="glyphicon glyphicon-plus"></i></button>
       <div id="att{{t.pk}}" class="collapse">
      {%endif%}
      &nbsp;&nbsp;&nbsp;&nbsp;Attachment (<a href="https://www.postgresql.org/message-id/attachment/{{ta.attachmentid}}/{{ta.filename}}">{{ta.filename}}</a>) at <a href="https://www.postgresql.org/message-id/{{ta.messageid}}">{{ta.date}}</a> from {{ta.author|hidemail}} (Patch: {{ta.ispatch|yesno:"Yes,No,Pending check"}})<br/>
      {%if forloop.last%}</div>{%endif%}
     {%endfor%}
     <div>
      {%for a in t.mailthreadannotation_set.all%}
       {%if forloop.first%}
        <h4>Annotations</h4>
        <table class="table table-bordered table-striped table-condensed small">
         <thead>
          <tr>
           <th>When</th>
           <th>Who</th>
           <th>Mail</th>
           <th>Annotation</th>
          </tr>
         </thead>
         <tbody>
       {%endif%}
       <tr>
        <td>{{a.date}}</td>
        <td style="white-space: nowrap">{{a.user_string}}</td>
        <td style="white-space: nowrap">From {{a.mailauthor}}<br/>at <a href="https://www.postgresql.org/message-id/{{a.msgid}}">{{a.maildate}}</a></td>
        <td width="99%">{{a.annotationtext}} <button type="button" class="close" title="Delete this annotation" onclick="deleteAnnotation({{a.id}})">&times;</button></td>
       </tr>
       {%if forloop.last%}
        </body>
        </table>
       {%endif%}
      {%endfor%}
      {%if user.is_authenticated%}<button class="btn btn-xs btn-default" onclick="addAnnotation({{t.id}})">Add annotation</button>{%endif%}
      {%if user.is_authenticated%}
       <div><button class="btn btn-default" onclick="attachThread({{cf.id}},{{patch.id}})">Attach thread</button></div>
      {%else%}
       <div><button class="btn btn-default" onclick="location.href='/account/login/?next=/{{cf.id}}/{{patch.id}}/%3Fattachthreadnow'">Attach New Thread</button></div>
      {%endif%}
     </div>
    </dd>
   {%endfor%}
  </dl>
 </td>
</tr>
