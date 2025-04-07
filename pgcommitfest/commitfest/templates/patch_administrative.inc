<div style="margin-bottom:5px;">
 <a class="btn btn-default" href="edit/">Edit</a>

 <div class="btn-group">
  <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Comment/Review <span class="caret"></span></a>
  <ul class="dropdown-menu">
   <li><a href="comment/">Comment</a>
    <li><a href="review/">Review</a>
    </ul>
   </div>

   <div class="btn-group">
    <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Change Status <span class="caret"></span></a>
    <ul class="dropdown-menu" role="menu">
     <li role="presentation" class="dropdown-header">Assign to:</li>
     <li role="presentation"><a href="status/review/">Reviewer</a></li>
     <li role="presentation"><a href="status/author/">Author</a></li>
     <li role="presentation"><a href="status/committer/">Committer</a></li>
     <li role="presentation" class="divider"></li>
     <li role="presentation" class="dropdown-header">Resolve:</li>
     <li role="presentation"><a href="close/reject/" onclick="return verify_reject()">Reject</a></li>
     <li role="presentation"><a href="close/withdrawn/" onclick="return verify_withdrawn()">Withdraw</a></li>
     <li role="presentation"><a href="close/feedback/" onclick="return verify_returned()">Return</a></li>
     <li role="presentation"><a href="close/committed/" onclick="return flagCommitted({%if patch.committer%}'{{patch.committer}}'{%elif is_committer%}'{{user.username}}'{%else%}null{%endif%})">Commit</a></li>
     <li role="presentation" class="divider"></li>
     <li role="presentation" class="dropdown-header">Move To:</li>
     {%if not cf.isfuture and workflow.future %}
      <li role="presentation">
       <a
        href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.future.id}}">
        {{workflow.future.name}}</a>
      </li>
     {%endif%}
     {%if not cf.isopen and workflow.open %}
      <li role="presentation">
       <a
        href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.open.id}}">
        {{workflow.open.name}}</a>
      </li>
     {%endif%}
     {%if not cf.isinprogress and workflow.progress %}
      <li role="presentation">
       <a
        href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.progress.id}}">
        {{workflow.progress.name}}</a>
      </li>
     {%endif%}
     {%if not cf.isparked and workflow.parked %}
      <li role="presentation">
       <a
        href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.parked.id}}">
        {{workflow.parked.name}}</a>
      </li>
     {%endif%}
    </ul>
   </div>

   {%if request.user.is_staff%}
    <div class="btn-group">
     <a class="btn btn-default dropdown-toggle" data-toggle="dropdown" href="#">Send private mail <span class="caret"></span></a>
     <ul class="dropdown-menu">
      <li><a href="send_email/?authors={{patch.id}}">Send mail to authors</a></li>
      <li><a href="send_email/?reviewers={{patch.id}}">Send mail to reviewers</a></li>
      <li><a href="send_email/?authors={{patch.id}}&reviewers={{patch.id}}">Send mail to authors and reviewers</a></li>
     </ul>
    </div>
   {%endif%}

  </div>
