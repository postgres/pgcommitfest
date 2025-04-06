{%load commitfest%}
<div class="workflow">
 <table class="table table-bordered">
 <thead>
  <tr>
   <th>Assign To</th>
   <th>Annotate</th>
   <th>Resolve</th>
   <th>Move To</th>
  </tr>
 </thead>
 <tbody>
  <tr>
  <!-- Change -->
  <td>
   {%if poc.status == poc.STATUS_AUTHOR %}
    <a class="btn btn-default" href="status/review/">Reviewer</a>
   {%endif%}
   {%if poc.status == poc.STATUS_REVIEW or poc.status == poc.STATUS_COMMITTER %}
    <a class="btn btn-default" href="status/author/">Author</a>
   {%endif%}
   {%if poc.status == poc.STATUS_REVIEW %}
    <a class="btn btn-default" href="status/committer/">Committer</a>
   {%endif%}
  </td>
  <!-- Annotate -->
  <td>
   <a class="btn btn-default" href="comment/">Comment</a>
   <a class="btn btn-default" href="review/">Review</a>
  </td>
  <!-- Resolve -->
  <td>
   {%if is_committer or is_author %}
    {%if is_committer %}
     <a class="btn btn-default" href="close/committed/" onclick="return flagCommitted({%if patch.committer%}'{{patch.committer}}'{%elif is_committer%}'{{user.username}}'{%else%}null{%endif%})">Commit</a>
     <a class="btn btn-default" href="close/reject/" onclick="return verify_reject()">Reject</a>
    {%endif%}
    {%if is_author %}
     <a class="btn btn-default" href="close/withdrawn/" onclick="return verify_withdrawn()">Withdraw</a>
    {%endif%}
   {%else%}
    <span>No Actions Available</span>
   {%endif%}
  </td>
  <!-- Move -->
  <td>
   {%if not cf.isfuture and workflow.future %}
    {%if True %}
     <a class="btn btn-default"
      href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.future.id}}">
     {{workflow.future.name}}</a>
    {%endif%}
   {%endif%}

   {%if not cf.isopen and workflow.open %}
    {%if is_committer %}
     <a class="btn btn-default"
      href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.open.id}}">
     {{workflow.open.name}}</a>
    {%endif%}
   {%endif%}

   {%if not cf.isinprogress and workflow.progress %}
    {%if is_committer %}
     <a class="btn btn-default"
      href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.progress.id}}">
     {{workflow.progress.name}}</a>
    {%endif%}
   {%endif%}

   {%if not cf.isparked and workflow.parked %}
    {%if is_author %}
     <a class="btn btn-default"
      href="transition/?fromcfid={{poc.commitfest.id}}&tocfid={{workflow.parked.id}}">
     {{workflow.parked.name}}</a>
    {%endif%}
   {%endif%}

  </td>
  </tr>

  <tr>
   <th>Author(s)</th>
   <th>Reviewer(s)</th>
   <th>Committer</th>
   <th>Status</th>
  </tr>

  <tr>
  <!-- Change -->
  <td>
   {%for author in authors %}
    <div>{{author.first_name}} {{author.last_name}}</div>
   {%endfor%}
   {%if is_author or is_committer %}
    <a class="btn btn-default " href="edit/">Edit Authors</a>
   {%endif%}
  </td>
  <!-- Annotate -->
  <td>
   {%for reviewer in reviewers %}
    <div>{{reviewer.first_name}} {{reviewer.last_name}}</div>
   {%endfor%}
   <div><a href="reviewer/{{is_reviewer|yesno:"remove,become"}}/" class="btn btn-default">{{is_reviewer|yesno:"Remove from reviewers,Become reviewer"}}</a></div>
  </td>
  <!-- Resolve -->
  <td>
   {%if patch.committer%}<div>{{patch.committer.fullname}}</div>{%endif%}
   {%if is_committer%}<div><a href="committer/{{is_this_committer|yesno:"remove,become"}}/" class="btn btn-default">{{is_this_committer|yesno:"Unclaim as committer,Claim as committer"}}</a></div>{%endif%}
  </td>
  <!-- Move -->
  <td>
   <div>
    <span class="label label-{{poc.commitfest.status|patchstatuslabel}}">{{poc.commitfest.statusstring}}</span>
    <span class="label label-{{poc.status|patchstatuslabel}}">{{poc.statusstring}}</span>
    <span><a href="edit/">Version</a>: </span> <span class="label label-default">{%if patch.targetversion%}{{patch.targetversion}}{%else%}N/A{%endif%}</span>
    {%if user.is_authenticated%}
     <span class="pull-right">Updates: <a href="{{is_subscribed|yesno:"unsubscribe,subscribe"}}/" class="btn btn-default">{{is_subscribed|yesno:"Unsubscribe,Subscribe"}}</a></span>
    {%endif%}
   </div>
   <div>
    <span><a href="edit/">Topic</a>: </span></span> <span>{{ patch.topic }}</span>
   </div>
   <div>
    <span>Last Modified:</span> <span>{{patch.modified}} ({% cfwhen patch.modified %})</span>
   </div>
  </td>
  </tr>
 </tbody>
 </table>
</div>
