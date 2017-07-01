use matthew_cole

if object_id('Event') is not null
	drop table [Event]
if object_id('SlackUser') is not null
	drop table SlackUser
if object_id('SlackUserToEvent') is not null
	drop table SlackUserToEvent;
if object_id('CreateSlackUser') is not null
	drop procedure CreateSlackUser
if object_id('AddUserToEvent') is not null
	drop procedure AddUserToEvent
if object_id('CreateEvent') is not null
	drop procedure CreateEvent
if object_id('GetUserEvent') is not null
	drop procedure GetUserEvent
if object_id('GetNextEvent') is not null
	drop procedure GetNextEvent
if object_id('GetUsersInEvent') is not null
	drop procedure GetUsersInEvent
if object_id('LeaveEvent') is not null
	drop procedure LeaveEvent

create table SlackUser
	(
	UserID			int				primary key identity(1,1),
	SlackUserID		varchar(15)		not null unique,
	[Name]			varchar(50)		not null
	)

create table [Event]
	(
	EventID				int				primary key identity(1,1),
	EventDescription	varchar(500),
	EventDate			date			default('2017-01-01'),
	EventTime			time			default('00:00:00')
	)

create table [SlackUserToEvent]
	(
	SlackUserID		varchar(15)		not null references SlackUser(SlackUserID),
	EventID			int				not null references [Event](EventID),
	primary key (SlackUserID, EventID)
	)

go
create proc CreateSlackUser
(
	@UserID		varchar(15),
	@Username	varchar(50)
)
as
begin
	if (not exists(select SlackUserID from SlackUser where SlackUserID = @UserID))
	begin
		insert into SlackUser
		values (@UserID, @Username)
		select SlackUserID, Name from SlackUser where SlackUserID = @UserID and [Name] = @Username
	end
	else
		select -1
end

go
create proc AddUserToEvent
(
	@UserID		varchar(15),
	@EventID	int
)
as
begin
	if (not exists(select SlackUserID from SlackUserToEvent where SlackUserID = @UserID and EventID = @EventID))
	begin
		insert into SlackUserToEvent
		values (@UserID, @EventID)
	end
end

go
create proc CreateEvent
(
	@UserID			varchar(15),
	@Description	varchar(500),
	@Date			date,
	@Time			time
)
as
begin
	declare @EventID int

	insert into [Event]
	values (@Description, @Date, @Time)

	set @EventID = @@IDENTITY
	exec AddUserToEvent @UserID, @EventID
end

go
create proc GetUserEvent
(	
	@UserID		varchar(15),
	@EventID	int
)
as
begin
	select [Event].EventID, EventDescription, EventDate, EventTime
	from [Event] join SlackUserToEvent		on [Event].EventID = SlackUserToEvent.EventID
	where SlackUserID = @UserID and [Event].EventID > @EventID
end

go
create proc GetNextEvent
(	@EventID int	) as
begin
	select EventID, EventDescription, EventDate, EventTime
	from [Event]
	where EventID = (select top 1 EventID from SlackUserToEvent where EventID > @EventID order by EventID)
end

go
create proc GetUsersInEvent
(	@EventID int	) as
begin
	select SlackUser.SlackUserID, [Name]
	from SlackUser join SlackUserToEvent	on SlackUser.SlackUserID = SlackUserToEvent.SlackUserID
	where [SlackUserToEvent].EventID = @EventID
end

go
create proc LeaveEvent
(	
	@UserID		varchar(15),
	@EventID	int
)
as
begin
	delete from SlackUserToEvent
	where EventID = @EventID and SlackUserID = @UserID

	if ((select count(*) from SlackUserToEvent where EventID = @EventID) < 1)
	begin
		delete from [Event]
		where EventID = @EventID
	end
end